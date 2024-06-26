# Copyright (C) 2013-2024 Catalyst Cloud Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from datetime import datetime
import os
from random import shuffle

import eventlet
from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import service
from oslo_service import threadgroup
from stevedore import driver
from stevedore import extension

from distil.db import api as db_api
from distil import exceptions
from distil.common import constants
from distil.common import general
from distil.common import openstack

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def filter_projects(projects):
    p_filtered = list()

    if CONF.collector.include_tenants:
        p_filtered = [p for p in projects if
                      p['name'] in CONF.collector.include_tenants]
    elif CONF.collector.ignore_tenants:
        p_filtered = [p for p in projects if
                      p['name'] not in CONF.collector.ignore_tenants]
    else:
        p_filtered = projects

    LOG.info("After filtering, %s project(s) left." % len(p_filtered))

    return p_filtered


class CollectorService(service.Service):
    def __init__(self):
        super(CollectorService, self).__init__()

        self.thread_grp = None

        self.validate_config()

        self.identifier = general.get_process_identifier()

        self.metrics_processors = []
        for ext in extension.ExtensionManager(
            'distil.collector.metrics',
            invoke_on_load=False,
        ):
            metrics_processor_class = ext.entry_point.load()
            metrics_processor = metrics_processor_class.load()
            if metrics_processor is not None:
                self.metrics_processors.append(metrics_processor)

        collector_args = {"metrics_processors": self.metrics_processors}
        self.collector = driver.DriverManager(
            'distil.collector',
            CONF.collector.collector_backend,
            invoke_on_load=True,
            invoke_kwds=collector_args
        ).driver

    def validate_config(self):
        include_tenants = set(CONF.collector.include_tenants)
        ignore_tenants = set(CONF.collector.ignore_tenants)

        if include_tenants & ignore_tenants:
            raise exceptions.InvalidConfig(
                "Duplicate tenants config in include_tenants and "
                "ignore_tenants."
            )

    def start(self):
        LOG.info("Starting collector service...")

        for metrics_processor in self.metrics_processors:
            metrics_processor.start()
        self.thread_grp = threadgroup.ThreadGroup()
        self.thread_grp.add_timer(CONF.collector.periodic_interval,
                                  self.collect_usage)
        super(CollectorService, self).start()

        LOG.info("Collector service started.")

    def stop(self):
        LOG.info("Stopping collector service gracefully...")

        if self.thread_grp:
            self.thread_grp.stop()
        for metrics_processor in self.metrics_processors:
            metrics_processor.stop()
        super(CollectorService, self).stop()

        LOG.info("Collector service stoped.")

    def reset(self):
        super(CollectorService, self).reset()
        logging.setup(CONF, 'distil-collector')

    def _get_projects_by_order(self, projects):
        if CONF.collector.project_order == 'ascending':
            return projects
        elif CONF.collector.project_order == 'descending':
            projects.reverse()
            return projects
        elif CONF.collector.project_order == 'random':
            shuffle(projects)
            return projects

    def collect_usage(self):
        # NOTE(dalees): oslo_service LoopingCallBase._run_loop does not handle
        # exceptions without ending the timer loop. So we gotta catch 'em all.
        try:
            return self._collect_usage()
        except Exception:
            LOG.exception(
                "Usage collection failed (trying again in %i seconds)",
                CONF.collector.periodic_interval,
            )
            # Pretend we succeeded and let the looping call retry
            # under normal intervals.
            return True

    def _collect_usage(self):
        LOG.info("Starting to collect usage...")
        collection_start = datetime.utcnow()
        collection_start_timestamp = (
            collection_start - datetime(1970, 1, 1)
        ).total_seconds()

        if CONF.collector.max_windows_per_cycle <= 0:
            LOG.info("Finished collecting usage with configuration "
                     "max_windows_per_cycle<=0.")
            return True

        # Update the last_run_start metric on all metrics processors.
        for metrics_processor in self.metrics_processors:
            metrics_processor.last_run_start(collection_start_timestamp)

        projects = openstack.get_projects(
            domains=CONF.collector.include_domains)
        valid_projects = filter_projects(projects)
        project_ids = [p['id'] for p in valid_projects]

        # For new created project, we use the earliest last collection time
        # among existing valid projects as the start time.
        last_collect = db_api.get_last_collect(project_ids).last_collected

        end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        if CONF.collect_end_time:
            end = datetime.strptime(CONF.collect_end_time, constants.iso_time)

        # Number of projects updated successfully.
        success_count = 0
        # Number of projects processed actually.
        processed_count = 0
        # Number of projects already up-to-date.
        updated_count = 0

        valid_projects = self._get_projects_by_order(valid_projects)
        for project in valid_projects:
            # Check if the project is being processed by other collector
            # instance. If no, will get a lock and continue processing,
            # otherwise just skip it.
            locks = db_api.get_project_locks(project['id'])
            if locks and locks[0].owner != self.identifier:
                LOG.debug(
                    "Project %s is being processed by collector %s." %
                    (project['id'], locks[0].owner)
                )
                continue

            try:
                with db_api.project_lock(project['id'], self.identifier):
                    processed_count += 1

                    # Add a project or get last_collected of existing project.
                    db_project = db_api.project_add(project, last_collect)
                    start = db_project.last_collected

                    windows = general.get_windows(start, end)
                    if not windows:
                        LOG.info(
                            "project %s(%s) already up-to-date.",
                            project['id'], project['name']
                        )
                        updated_count += 1
                        continue

                    if self.collector.collect_usage(project, windows):
                        success_count += 1
            except exceptions.DuplicateException as e:
                LOG.warning(
                    'Obtaining the project lock failed: %s. Process: %s',
                    e,
                    self.identifier,
                )

            # Co-operatively yield to give other threads
            # (mainly metrics processors) a chance to run.
            eventlet.sleep()

        LOG.info("Finished collecting usage for %s projects." % success_count)
        collection_end = datetime.utcnow()
        collection_end_timestamp = (
            collection_end - datetime(1970, 1, 1)
        ).total_seconds()
        collection_taken = collection_end - collection_start
        LOG.info("Collection time was: %ss." % collection_taken.seconds)

        # Update the last_run_end and last_run_duration_seconds metric
        # on all metrics processors.
        for metrics_processor in self.metrics_processors:
            metrics_processor.last_run_end(collection_end_timestamp)
            metrics_processor.last_run_duration_seconds(
                collection_taken.total_seconds(),
            )

        # If we start distil-collector manually with 'collect_end_time' param
        # specified, the service should be stopped automatically after all
        # projects usage collection is up-to-date.
        if CONF.collect_end_time and updated_count == processed_count:
            self.stop()
            os.kill(os.getpid(), 9)

        return True
