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
import os

import mock

from decimal import Decimal

from distil.collector import base as collector_base
from distil.common import constants
from distil.db import api as db_api
from distil.service import collector
from distil.tests.unit import base
from distil.tests.unit.collector.utils import FakeCeilometerSample


class CollectorBaseTest(base.DistilWithDbTestCase):
    def setUp(self):
        super(CollectorBaseTest, self).setUp()

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

    @mock.patch('distil.common.openstack.get_root_volume')
    @mock.patch('distil.common.openstack.get_image')
    def test_get_os_distro_instance_active_boot_from_image(self,
                                                           mock_get_image,
                                                           mock_get_root):
        mock_get_root.return_value = None

        class Image(object):
            def __init__(self):
                self.os_distro = 'linux'

        mock_get_image.return_value = Image()

        entry = {
            'resource_id': 'fake_vm_id',
            'metadata': {
                'image_ref_url': 'http://cloud:9292/images/1-2-3-4'
            }
        }

        collector = collector_base.BaseCollector()
        os_distro = collector._get_os_distro(entry)

        mock_get_image.assert_called_once_with('1-2-3-4')

        self.assertEqual('linux', os_distro)

    @mock.patch('distil.common.openstack.get_root_volume',
                side_effect=Exception())
    @mock.patch('distil.common.openstack.get_image')
    def test_get_os_distro_instance_delete_boot_from_image(self,
                                                           mock_get_image,
                                                           mock_get_root):
        mock_get_root.return_value = None

        class Image(object):
            def __init__(self):
                self.os_distro = 'linux'

        mock_get_image.return_value = Image()

        entry = {
            'resource_id': 'fake_vm_id',
            'metadata': {
                'image_ref_url': 'http://cloud:9292/images/1-2-3-4'
            }
        }

        collector = collector_base.BaseCollector()
        os_distro = collector._get_os_distro(entry)

        mock_get_image.assert_called_once_with('1-2-3-4')

        self.assertEqual('linux', os_distro)

    @mock.patch('distil.common.openstack.get_root_volume')
    def test_get_os_distro_instance_active_boot_from_volume(self,
                                                            mock_get_root):
        class Volume(object):
            def __init__(self):
                self.volume_image_metadata = {'os_distro': 'linux'}

        mock_get_root.return_value = Volume()

        entry = {
            'resource_id': 'fake_vm_id',
            'metadata': {
                'image_ref_url': None
            }
        }

        collector = collector_base.BaseCollector()
        os_distro = collector._get_os_distro(entry)

        mock_get_root.assert_called_once_with('fake_vm_id')

        self.assertEqual('linux', os_distro)

    @mock.patch('distil.common.openstack.get_root_volume',
                side_effect=Exception())
    def test_get_os_distro_instance_delete_boot_from_volume(self,
                                                            mock_get_root):
        entry = {
            'resource_id': 'fake_vm_id',
            'metadata': {
                'image_ref_url': None
            }
        }

        collector = collector_base.BaseCollector()
        os_distro = collector._get_os_distro(entry)

        self.assertEqual('unknown', os_distro)

    @mock.patch('distil.common.openstack.get_ceilometer_client')
    def test_collect_usage_meter_exception(self, mock_cclient):
        cclient = mock.Mock()
        cclient.new_samples.list.side_effect = Exception('get_meter exception!')
        mock_cclient.return_value = cclient

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {'name': 'fake_project', 'id': '123'},
            [(datetime.utcnow() - timedelta(hours=1), datetime.utcnow())]
        )

        self.assertFalse(ret)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_volume_fixed(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_volume_fixed"
        resource_id = "fake_cluster_id"
        expected_volume = 2

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_volume_fixed",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"node_count": str(expected_volume)},
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertTrue(ret)

        expected = [
            {
                "tenant_id": project,
                "resource_id": resource_id,
                "service": "coe1.worker",
                "unit": "worker",
                "volume": Decimal(expected_volume),
            },
        ]
        actual = [
            usage_entry.to_dict()
            for usage_entry in db_api.usage_get(
                project_id=project,
                start_at=start,
                end_at=end,
            )
        ]

        self.assertEqual(expected, actual)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_volume_source(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_volume_source"
        resource_id = "fake_cluster_id"
        expected_volume = 3

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_volume_source",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"node_count": str(expected_volume)},
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertTrue(ret)

        expected = [
            {
                "tenant_id": project,
                "resource_id": resource_id,
                "service": "coe1.worker",
                "unit": "worker",
                "volume": Decimal(expected_volume),
            },
        ]
        actual = [
            usage_entry.to_dict()
            for usage_entry in db_api.usage_get(
                project_id=project,
                start_at=start,
                end_at=end,
            )
        ]

        self.assertEqual(expected, actual)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_volume_source_notfound(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_volume_source_invalid"
        resource_id = "fake_cluster_id"

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_volume_source",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={},  # node_count is not in the metadata.
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertFalse(ret)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_volume_source_invalid_type(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_volume_source_invalid_type"
        resource_id = "fake_cluster_id"

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_volume_source",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"node_count": "string"},  # Cannot be converted to a float.
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertFalse(ret)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_volume_source_invalid_type(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_volume_source_invalid_type"
        resource_id = "fake_cluster_id"

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_volume_source",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"node_count": "string"},  # Cannot be converted to a float.
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertFalse(ret)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_volume_sources(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_volume_sources"
        resource_id = "fake_cluster_id"
        expected_volume = 3

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_volume_sources",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"node_count": str(expected_volume)},
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertTrue(ret)

        expected = [
            {
                "tenant_id": project,
                "resource_id": resource_id,
                "service": "coe1.worker",
                "unit": "worker",
                "volume": Decimal(expected_volume),
            },
        ]
        actual = [
            usage_entry.to_dict()
            for usage_entry in db_api.usage_get(
                project_id=project,
                start_at=start,
                end_at=end,
            )
        ]

        self.assertEqual(expected, actual)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_volume_sources_first_notfound(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_volume_sources_first_notfound"
        resource_id = "fake_cluster_id"
        expected_volume = 3

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_volume_sources_first_notfound",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"node_count": str(expected_volume)},
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertTrue(ret)

        expected = [
            {
                "tenant_id": project,
                "resource_id": resource_id,
                "service": "coe1.worker",
                "unit": "worker",
                "volume": Decimal(expected_volume),
            },
        ]
        actual = [
            usage_entry.to_dict()
            for usage_entry in db_api.usage_get(
                project_id=project,
                start_at=start,
                end_at=end,
            )
        ]

        self.assertEqual(expected, actual)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_volume_sources_undefined(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_volume_sources_undefined"
        resource_id = "fake_cluster_id"
        expected_volume = 1

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_volume_sources_undefined",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id,
                meter="cim.coe.cluster",
                volume=expected_volume,
                timestamp=timestamp,
                metadata={"node_count": "3"},
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertTrue(ret)

        expected = [
            {
                "tenant_id": project,
                "resource_id": resource_id,
                "service": "coe1.worker",
                "unit": "worker",
                "volume": Decimal(expected_volume),
            },
        ]
        actual = [
            usage_entry.to_dict()
            for usage_entry in db_api.usage_get(
                project_id=project,
                start_at=start,
                end_at=end,
            )
        ]

        self.assertEqual(expected, actual)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_filters_contains(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_filters_contains"
        resource_id1 = "fake_cluster_id1"
        resource_id2 = "fake_cluster_id2"
        expected_volume = 1

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_filters_contains",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id1,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"status": "CREATE_COMPLETE"},
            ),
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id2,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"status": "CREATE_FAILED"},
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertTrue(ret)

        expected = [
            {
                "tenant_id": project,
                "resource_id": resource_id1,
                "service": "coe1.cluster",
                "unit": "hour",
                "volume": Decimal(expected_volume),
            },
        ]
        actual = [
            usage_entry.to_dict()
            for usage_entry in db_api.usage_get(
                project_id=project,
                start_at=start,
                end_at=end,
            )
        ]

        self.assertEqual(expected, actual)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_filters_not_contains(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_filters_contains"
        resource_id1 = "fake_cluster_id1"
        resource_id2 = "fake_cluster_id2"
        expected_volume = 1

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_filters_not_contains",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id1,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"status": "CREATE_COMPLETE"},
            ),
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id2,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"status": "CREATE_FAILED"},
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertTrue(ret)

        expected = [
            {
                "tenant_id": project,
                "resource_id": resource_id1,
                "service": "coe1.cluster",
                "unit": "hour",
                "volume": Decimal(expected_volume),
            },
        ]
        actual = [
            usage_entry.to_dict()
            for usage_entry in db_api.usage_get(
                project_id=project,
                start_at=start,
                end_at=end,
            )
        ]

        self.assertEqual(expected, actual)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_filters_comparator(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_filters_comparator"
        resource_id1 = "fake_cluster_id1"
        resource_id2 = "fake_cluster_id2"
        expected_volume = 3

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_filters_comparator",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id1,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"node_count": "3"},
            ),
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id2,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"node_count": "2"},
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertTrue(ret)

        expected = [
            {
                "tenant_id": project,
                "resource_id": resource_id1,
                "service": "coe1.worker",
                "unit": "worker",
                "volume": Decimal(expected_volume),
            },
        ]
        actual = [
            usage_entry.to_dict()
            for usage_entry in db_api.usage_get(
                project_id=project,
                start_at=start,
                end_at=end,
            )
        ]

        self.assertEqual(expected, actual)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_filters_multiple(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_filters_multiple"
        resource_id1 = "fake_cluster_id1"
        resource_id2 = "fake_cluster_id2"
        expected_volume = 3

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_filters_multiple",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id1,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"node_count": "3"},
            ),
            FakeCeilometerSample(
                project_id=project,
                resource_id=resource_id2,
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"node_count": "2"},
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertTrue(ret)

        expected = [
            {
                "tenant_id": project,
                "resource_id": resource_id1,
                "service": "coe1.worker",
                "unit": "worker",
                "volume": Decimal(expected_volume),
            },
        ]
        actual = [
            usage_entry.to_dict()
            for usage_entry in db_api.usage_get(
                project_id=project,
                start_at=start,
                end_at=end,
            )
        ]

        self.assertEqual(expected, actual)

    @mock.patch("distil.common.openstack.get_ceilometer_client")
    def test_collect_usage_filters_all_filtered(self, mock_cclient):
        end = datetime.utcnow()
        timestamp = end - timedelta(minutes=30)
        start = end - timedelta(hours=1)
        project = "test_collect_usage_filters_all_filtered"

        self.conf.set_default(
            "meter_mappings_file",
            os.path.join(
                os.environ["DISTIL_TESTS_CONFIGS_DIR"],
                "test_collect_usage_filters_contains",
                "meter_mappings.yaml",
            ),
            group="collector",
        )

        cclient = mock.Mock()
        cclient.new_samples.list.return_value = [
            FakeCeilometerSample(
                project_id=project,
                resource_id="fake_cluster_id",
                meter="cim.coe.cluster",
                volume=1,
                timestamp=timestamp,
                metadata={"status": "CREATE_FAILED"},
            ),
        ]
        mock_cclient.return_value = cclient

        db_api.project_add({"id": project, "name": project, "description": project})

        srv = collector.CollectorService()
        ret = srv.collector.collect_usage(
            {"name": project, "id": project},
            [(start, end)],
        )

        self.assertTrue(ret)

        expected = []
        actual = [
            usage_entry.to_dict()
            for usage_entry in db_api.usage_get(
                project_id=project,
                start_at=start,
                end_at=end,
            )
        ]

        self.assertEqual(expected, actual)
