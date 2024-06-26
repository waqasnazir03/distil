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
from datetime import timedelta
import hashlib
import json
import os
from random import shuffle

import mock

from distil.collector import base as collector_base
from distil.common import constants
from distil.db.sqlalchemy import api as db_api
from distil.helpers import get_max_last_collected
from distil.service import collector
from distil.tests.unit import base


class CollectorTest(base.DistilWithDbTestCase):
    def setUp(self):
        super(CollectorTest, self).setUp()

        self.conf.set_default(
            "max_collection_start_age",
            24,
            group="collector",
        )

        meter_mapping_file = os.path.join(
            os.environ["DISTIL_TESTS_CONFIGS_DIR"],
            'meter_mappings.yaml'
        )
        self.conf.set_default(
            'meter_mappings_file',
            meter_mapping_file,
            group='collector'
        )

        transformer_file = os.path.join(
            os.environ["DISTIL_TESTS_CONFIGS_DIR"],
            'transformer.yaml'
        )
        self.conf.set_default(
            'transformer_file',
            transformer_file,
            group='collector'
        )

    @mock.patch('distil.collector.base.BaseCollector.get_meter')
    def test_collect_swift_resource_id(self, mock_get_meter):
        project_id = 'fake_project_id'
        project_name = 'fake_project'
        project = {'id': project_id, 'name': project_name}
        start_time = datetime.strptime(
            '2017-02-27 00:00:00',
            "%Y-%m-%d %H:%M:%S"
        )
        end_time = datetime.strptime(
            '2017-02-27 01:00:00',
            "%Y-%m-%d %H:%M:%S"
        )

        # Add project to db in order to satisfy the foreign key constraint of
        # UsageEntry
        db_api.project_add(
            {
                'id': project_id,
                'name': 'fake_project',
                'description': 'project for test'
            }
        )

        container_name = 'my_container'
        resource_id = '%s/%s' % (project_id, container_name)
        resource_id_hash = hashlib.md5(resource_id.encode('utf-8')).hexdigest()

        mock_get_meter.return_value = [
            {
                'resource_id': resource_id,
                'source': 'openstack',
                'volume': 1024
            }
        ]

        collector = collector_base.BaseCollector()
        collector.collect_usage(project, [(start_time, end_time)])

        resources = db_api.resource_get_by_ids(project_id, [resource_id_hash])
        res_info = json.loads(resources[0].info)

        self.assertEqual(1, len(resources))
        self.assertEqual(container_name, res_info['name'])

        entries = db_api.usage_get(project_id, start_time, end_time)

        self.assertEqual(1, len(entries))
        self.assertEqual(resource_id_hash, entries[0].resource_id)

    @mock.patch(
        'distil.collector.ceilometer.CeilometerCollector.collect_usage')
    @mock.patch('distil.common.openstack.get_ceilometer_client')
    @mock.patch('distil.common.openstack.get_projects')
    def test_last_collect_new_project(self, mock_get_projects, mock_cclient,
                                      mock_collect_usage):
        utcnow = datetime.utcnow()
        max_last_collected = (
            utcnow.replace(minute=0, second=0, microsecond=0)
            - timedelta(hours=self.conf.collector.max_collection_start_age)
        )

        # Assume project_2 is a new project that doesn't exist in distil db.
        mock_get_projects.return_value = [
            {'id': '111', 'name': 'project_1', 'description': 'existing'},
            {'id': '222', 'name': 'project_2', 'description': 'new'},
        ]

        # Insert project_0 and project_1 in the database, project_0 is not in
        # keystone anymore.
        db_api.project_add(
            {
                'id': '000',
                'name': 'project_0',
                'description': 'deleted',
            },
        )
        db_api.project_add(
            {
                'id': '111',
                'name': 'project_1',
                'description': 'existing',
            },
        )

        def _get_max_last_collected(*args):
            with mock.patch("datetime.datetime") as mock_datetime:
                mock_datetime.utcnow.return_value = utcnow
                return get_max_last_collected(*args)

        with mock.patch(
            "distil.db.sqlalchemy.api.get_max_last_collected",
            side_effect=_get_max_last_collected,
        ):
            svc = collector.CollectorService()
            svc.collect_usage()

        self.assertEqual(2, mock_collect_usage.call_count)
        self.assertEqual(
            [
                mock.call(
                    {
                        "id": "111",
                        "name": "project_1",
                        "description": "existing",
                    },
                    [
                        (
                            max_last_collected,
                            max_last_collected + timedelta(hours=1),
                        ),
                    ],
                ),
                mock.call(
                    {
                        "id": "222",
                        "name": "project_2",
                        "description": "new",
                    },
                    [
                        (
                            max_last_collected,
                            max_last_collected + timedelta(hours=1),
                        ),
                    ],
                ),
            ],
            mock_collect_usage.call_args_list,
        )

    @mock.patch(
        'distil.collector.ceilometer.CeilometerCollector.collect_usage')
    @mock.patch('distil.common.openstack.get_ceilometer_client')
    @mock.patch('distil.common.openstack.get_projects')
    def test_last_collect_new_project_created_on(
        self,
        mock_get_projects,
        mock_cclient,
        mock_collect_usage,
    ):
        utcnow = datetime.utcnow()
        current_hour = utcnow.replace(minute=0, second=0, microsecond=0)
        max_last_collected = current_hour - timedelta(
            hours=self.conf.collector.max_collection_start_age,
        )

        project1_metadata = {
            "id": "111",
            "name": "project_1",
            "description": "no created_on",
        }
        project2_metadata = {
            "id": "222",
            "name": "project_2",
            "description": "has created_on",
            "created_on": (utcnow - timedelta(hours=1)).strftime(constants.iso_time),
        }

        mock_get_projects.return_value = [project1_metadata, project2_metadata]

        db_api.project_add(project1_metadata)
        db_api.project_add(project2_metadata)

        def _get_max_last_collected(*args):
            with mock.patch("datetime.datetime") as mock_datetime:
                mock_datetime.utcnow.return_value = utcnow
                return get_max_last_collected(*args)

        with mock.patch(
            "distil.db.sqlalchemy.api.get_max_last_collected",
            side_effect=_get_max_last_collected,
        ):
            svc = collector.CollectorService()
            svc.collect_usage()

        self.assertEqual(2, mock_collect_usage.call_count)
        self.assertEqual(
            [
                mock.call(
                    project1_metadata,
                    [
                        (
                            max_last_collected,
                            max_last_collected + timedelta(hours=1),
                        ),
                    ],
                ),
                mock.call(
                    project2_metadata,
                    [(current_hour - timedelta(hours=1), current_hour)],
                ),
            ],
            mock_collect_usage.call_args_list,
        )

    @mock.patch('distil.common.openstack.get_ceilometer_client')
    @mock.patch('distil.common.openstack.get_projects')
    @mock.patch('distil.db.api.get_project_locks')
    def test_project_order_ascending(self, mock_get_lock, mock_get_projects,
                                     mock_cclient):
        mock_get_projects.return_value = [
            {'id': '111', 'name': 'project_1', 'description': ''},
            {'id': '222', 'name': 'project_2', 'description': ''},
            {'id': '333', 'name': 'project_3', 'description': ''},
            {'id': '444', 'name': 'project_4', 'description': ''},
        ]

        # Insert a project in the database in order to get last_collect time.
        db_api.project_add(
            {
                'id': '111',
                'name': 'project_1',
                'description': '',
            },
            datetime.utcnow() - timedelta(hours=2)
        )

        svc = collector.CollectorService()
        svc.collector = mock.Mock()
        svc.collect_usage()

        expected_list = ['111', '222', '333', '444']
        actual_list = [call_args[0][0]
                       for call_args in mock_get_lock.call_args_list]
        self.assertEqual(expected_list, actual_list)

    @mock.patch('distil.common.openstack.get_ceilometer_client')
    @mock.patch('distil.common.openstack.get_projects')
    @mock.patch('distil.db.api.get_project_locks')
    def test_project_order_descending(self, mock_get_lock, mock_get_projects,
                                      mock_cclient):
        self.override_config('collector', project_order='descending')

        mock_get_projects.return_value = [
            {'id': '111', 'name': 'project_1', 'description': ''},
            {'id': '222', 'name': 'project_2', 'description': ''},
            {'id': '333', 'name': 'project_3', 'description': ''},
            {'id': '444', 'name': 'project_4', 'description': ''},
        ]

        # Insert a project in the database in order to get last_collect time.
        db_api.project_add(
            {
                'id': '111',
                'name': 'project_1',
                'description': '',
            },
            datetime.utcnow() - timedelta(hours=2)
        )

        svc = collector.CollectorService()
        svc.collector = mock.Mock()
        svc.collect_usage()

        expected_list = ['444', '333', '222', '111']
        actual_list = [call_args[0][0]
                       for call_args in mock_get_lock.call_args_list]
        self.assertEqual(expected_list, actual_list)

    @mock.patch('distil.common.openstack.get_ceilometer_client')
    @mock.patch('distil.service.collector.shuffle')
    @mock.patch('distil.common.openstack.get_projects')
    @mock.patch('distil.db.api.get_project_locks')
    def test_project_order_random(self, mock_get_lock, mock_get_projects,
                                  mock_shuffle, mock_cclient):
        self.override_config('collector', project_order='random')

        mock_get_projects.return_value = [
            {'id': '111', 'name': 'project_1', 'description': ''},
            {'id': '222', 'name': 'project_2', 'description': ''},
            {'id': '333', 'name': 'project_3', 'description': ''},
            {'id': '444', 'name': 'project_4', 'description': ''},
        ]

        shuffle_list = []
        def _shuffle(x):
            shuffle(x)
            shuffle_list.extend(x)
        mock_shuffle.side_effect = _shuffle

        # Insert a project in the database in order to get last_collect time.
        db_api.project_add(
            {
                'id': '111',
                'name': 'project_1',
                'description': '',
            },
            datetime.utcnow() - timedelta(hours=2)
        )

        svc = collector.CollectorService()
        svc.collector = mock.Mock()
        svc.collect_usage()

        expected_list = [project['id'] for project in shuffle_list]
        actual_list = [call_args[0][0]
                       for call_args in mock_get_lock.call_args_list]
        self.assertEqual(expected_list, actual_list)

    @mock.patch('os.kill')
    @mock.patch('distil.common.openstack.get_ceilometer_client')
    @mock.patch('distil.common.openstack.get_projects')
    def test_collect_with_end_time(self, mock_get_projects, mock_cclient,
                                   mock_kill):
        end_time = datetime.utcnow() + timedelta(hours=0.5)
        end_time_str = end_time.strftime("%Y-%m-%dT%H:00:00")
        self.override_config(collect_end_time=end_time_str)

        mock_get_projects.return_value = [
            {
                'id': '111',
                'name': 'project_1',
                'description': 'description'
            }
        ]
        # Insert the project info in the database.
        db_api.project_add(
            {
                'id': '111',
                'name': 'project_1',
                'description': '',
            },
            datetime.utcnow()
        )

        srv = collector.CollectorService()
        srv.thread_grp = mock.Mock()
        srv.collect_usage()

        self.assertEqual(1, srv.thread_grp.stop.call_count)
        self.assertEqual(1, mock_kill.call_count)
