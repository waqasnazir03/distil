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
from platform import python_version

import eventlet
from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import wsgi
from pbr.version import VersionInfo
from pkg_resources import get_distribution
from prometheus_client import CollectorRegistry
from prometheus_client import Counter
from prometheus_client import Gauge
from prometheus_client import Info
from prometheus_client import make_wsgi_app
from sqlalchemy import __version__ as sqlalchemy_version

from distil.collector.metrics.base import BaseCollectorMetrics
from distil.version import version_info as distil_version_info

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class PrometheusCollectorMetrics(BaseCollectorMetrics):
    """
    Prometheus exporter for Distil Collector.
    """

    def __init__(self, host, port):
        """
        Initialise the Distil Collector Prometheus exporter
        and seed the metrics with initial values.
        """
        # Bind host and port for the Prometheus exporter WSGI server.
        self.host = host
        self.port = port
        # WSGI server object reference.
        self._server = None
        # Prometheus metric collector registry. All metrics are binded
        # to the registry, which is then mapped to the exporter.
        self.registry = CollectorRegistry()
        # Distil Collector build information metric.
        # Mostly exports the versions of various packages and runtimes.
        self._build_info = Info(
            name="distil_collector_build",
            documentation="Distil Collector build information",
            registry=self.registry,
        )
        self._build_info.info(
            {
                "version": distil_version_info.version_string(),
                "ceilometer_client_version": VersionInfo(
                    "python-ceilometerclient",
                ).version_string(),
                "cinder_client_version": VersionInfo(
                    "python-cinderclient",
                ).version_string(),
                "glance_client_version": VersionInfo(
                    "python-glanceclient",
                ).version_string(),
                "keystone_client_version": VersionInfo(
                    "python-keystoneclient",
                ).version_string(),
                "keystone_middleware_version": VersionInfo(
                    "keystonemiddleware",
                ).version_string(),
                "keystone_auth1_version": VersionInfo(
                    "keystoneauth1",
                ).version_string(),
                "neutron_client_version": VersionInfo(
                    "python-neutronclient",
                ).version_string(),
                "nova_client_version": VersionInfo(
                    "python-novaclient",
                ).version_string(),
                "oslo_cache_version": VersionInfo(
                    "oslo.cache",
                ).version_string(),
                "oslo_config_version": VersionInfo(
                    "oslo.config",
                ).version_string(),
                "oslo_context_version": VersionInfo(
                    "oslo.context",
                ).version_string(),
                "oslo_db_version": VersionInfo(
                    "oslo.db",
                ).version_string(),
                "oslo_i18n_version": VersionInfo(
                    "oslo.i18n",
                ).version_string(),
                "oslo_log_version": VersionInfo(
                    "oslo.log",
                ).version_string(),
                "oslo_policy_version": VersionInfo(
                    "oslo.policy",
                ).version_string(),
                "oslo_serialization_version": VersionInfo(
                    "oslo.serialization",
                ).version_string(),
                "oslo_service_version": VersionInfo(
                    "oslo.service",
                ).version_string(),
                "oslo_utils_version": VersionInfo(
                    "oslo.utils",
                ).version_string(),
                "sqlalchemy_version": sqlalchemy_version,
                "eventlet_version": eventlet.__version__,
                "prometheus_client_version": get_distribution(
                    "prometheus-client",
                ).version,
                "python_version": python_version(),
            },
        )
        # Start timestamp for the latest collection run.
        # Seeded with the current time on creation.
        run_start = _get_utcnow_timestamp()
        self._last_run_start = Gauge(
            name="distil_collector_last_run_start",
            documentation=(
                "Unix timestamp for the latest collection run's start time"
            ),
            registry=self.registry,
        )
        self.last_run_start(run_start)
        # Finish timestamp for the latest collection run.
        # Seeded with the current time on creation.
        run_end = _get_utcnow_timestamp()
        self._last_run_end = Gauge(
            name="distil_collector_last_run_end",
            documentation=(
                "Unix timestamp for the latest collection run's end time"
            ),
            registry=self.registry,
        )
        self.last_run_end(run_end)
        # Duration of the latest collection run, in seconds.
        # Seeded with the difference between the initial
        # last_run_end and last_run_start value.
        self._last_run_duration_seconds = Gauge(
            name="distil_collector_last_run_duration_seconds",
            documentation="Latest collection run's duration in seconds",
            registry=self.registry,
        )
        self.last_run_duration_seconds(run_end - run_start)
        # Aggregate usage counter, for each service under each project.
        # Gets created as projects get collected.
        self._usage_total = Counter(
            name="distil_collector_usage_total",
            documentation=(
                "Total usage under each service for a given project"
            ),
            labelnames=("project_id", "service", "unit"),
            registry=self.registry,
        )

    @classmethod
    def load(cls):
        """
        Create the Prometheus Exporter object.
        If it should not be created (e.g. disabled in config), return None.
        """
        if CONF.collector.enable_exporter:
            return cls(
                host=CONF.collector.exporter_host,
                port=CONF.collector.exporter_port,
            )
        return None

    def start(self):
        """
        Start the Prometheus Exporter.
        """
        if not self._server:
            LOG.info("Starting Prometheus exporter...")
            _server = wsgi.Server(
                conf=CONF,
                name="distil-collector-exporter",
                app=make_wsgi_app(registry=self.registry),
                host=self.host,
                port=self.port,
                logger_name=__name__,
            )
            _server.start()
            self._server = _server
            LOG.info("Prometheus exporter started.")

    def stop(self):
        """
        Stop the Prometheus Exporter.
        """
        if self._server:
            LOG.info("Stopping Prometheus exporter...")
            self._server.stop()
            self._server = None
            LOG.info("Prometheus exporter stopped.")

    def last_run_start(self, timestamp):
        """
        Update the Unix timestamp for the latest run's start time.
        """
        LOG.debug(
            (
                "Setting Prometheus gauge 'distil_collector_last_run_start' "
                "to value: %f"
            ),
            timestamp,
        )
        self._last_run_start.set(timestamp)

    def last_run_end(self, timestamp):
        """
        Update the Unix timestamp for the latest run's start time.
        """
        LOG.debug(
            (
                "Setting Prometheus gauge 'distil_collector_last_run_end' "
                "to value: %f"
            ),
            timestamp,
        )
        self._last_run_end.set(timestamp)

    def last_run_duration_seconds(self, duration):
        """
        Update the last collection run's duration, in seconds.
        """
        LOG.debug(
            (
                "Setting Prometheus gauge "
                "'distil_collector_last_run_duration_seconds' to value: %f"
            ),
            duration,
        )
        self._last_run_duration_seconds.set(duration)

    def usage(
        self,
        project_id,
        service,
        unit,
        resource_id,
        start,
        end,
        volume,
    ):
        """
        Add the collected usage entry to the service-level aggregate counter.
        """
        LOG.debug(
            (
                "Increasing Prometheus counter 'distil_collector_usage_total"
                '{project_id="%s",service="%s",unit="%s"}\' '
                "by: %f"
            ),
            project_id,
            service,
            unit,
            volume,
        )
        self._usage_total.labels(
            project_id=project_id,
            service=service,
            unit=unit,
        ).inc(volume)


def _get_utcnow_timestamp():
    """
    Return the current time in the UTC timezone as a Unix timestamp.
    """

    # TODO(callumdickinson): When upgrading to Python 3, replace with:
    #   datetime.now(tz=timezone.utc).timestamp()
    return (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
