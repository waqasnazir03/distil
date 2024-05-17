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

import datetime

import mock

from distil.common.constants import date_format
from distil.common import general
from distil.common import openstack
from distil.tests.unit import base
from distil.transformer import get_transformer

p = lambda t: datetime.datetime.strptime(t, date_format)


class FAKE_DATA:
    t0 = p('2014-01-01T00:00:00')
    t0_10 = p('2014-01-01T00:10:00')
    t0_20 = p('2014-01-01T00:30:00')
    t0_30 = p('2014-01-01T00:30:00')
    t0_40 = p('2014-01-01T00:40:00')
    t0_50 = p('2014-01-01T00:50:00')
    t1 = p('2014-01-01T01:00:00')


@mock.patch.object(general, "get_transformer_config", lambda *args, **kwargs: {})
class TestNumboolTransformer(base.DistilTestCase):
    transformer_name = "numbool"

    def test_all_different_values(self):
        """
        Tests that the transformer correctly sets the volume to 1
        when all values are different.
        """

        data = [
            {"timestamp": FAKE_DATA.t0.isoformat(), "volume": 12},
            {"timestamp": FAKE_DATA.t0_10.isoformat(), "volume": 3},
            {"timestamp": FAKE_DATA.t0_20.isoformat(), "volume": 7},
            {"timestamp": FAKE_DATA.t0_30.isoformat(), "volume": 3},
            {"timestamp": FAKE_DATA.t0_40.isoformat(), "volume": 25},
            {"timestamp": FAKE_DATA.t0_50.isoformat(), "volume": 2},
            {"timestamp": FAKE_DATA.t1.isoformat(), "volume": 6},
        ]

        xform = get_transformer(self.transformer_name)
        usage = xform.transform_usage("some_meter", data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({"some_meter": 1}, usage)

    def test_all_same_values(self):
        """
        Tests that that transformer correctly sets the volume to 1
        when all values are the same.
        """

        data = [
            {"timestamp": FAKE_DATA.t0, "volume": 25},
            {"timestamp": FAKE_DATA.t0_30, "volume": 25},
            {"timestamp": FAKE_DATA.t1, "volume": 25},
        ]

        xform = get_transformer(self.transformer_name)
        usage = xform.transform_usage("some_meter", data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({"some_meter": 1}, usage)

    def test_none_value(self):
        """
        Tests that that transformer correctly handles a None value.
        """

        data = [
            {"timestamp": FAKE_DATA.t0, "volume": None},
        ]

        xform = get_transformer(self.transformer_name)
        usage = xform.transform_usage("some_meter", data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({"some_meter": 0}, usage)

    def test_none_and_other_values(self):
        """
        Tests that that transformer correctly handles a None value
        mixed with non-None values.
        """

        data = [
            {"timestamp": FAKE_DATA.t0, "volume": None},
            {"timestamp": FAKE_DATA.t0_30, "volume": 25},
            {"timestamp": FAKE_DATA.t1, "volume": 27},
        ]

        xform = get_transformer(self.transformer_name)
        usage = xform.transform_usage("some_meter", data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({"some_meter": 1}, usage)

    def test_zero_value(self):
        """
        Tests that that transformer correctly handles a zero value.
        """

        data = [
            {"timestamp": FAKE_DATA.t0, "volume": 0},
        ]

        xform = get_transformer(self.transformer_name)
        usage = xform.transform_usage("some_meter", data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({"some_meter": 0}, usage)

    def test_none_and_other_values(self):
        """
        Tests that that transformer correctly handles a zero value
        mixed with non-zero values.
        """

        data = [
            {"timestamp": FAKE_DATA.t0, "volume": 0},
            {"timestamp": FAKE_DATA.t0_30, "volume": 25},
            {"timestamp": FAKE_DATA.t1, "volume": 27},
        ]

        xform = get_transformer(self.transformer_name)
        usage = xform.transform_usage("some_meter", data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({"some_meter": 1}, usage)

    def test_negative_value(self):
        """
        Tests that that transformer correctly handles a negative value.
        """

        data = [
            {"timestamp": FAKE_DATA.t0, "volume": -1},
        ]

        xform = get_transformer(self.transformer_name)
        usage = xform.transform_usage("some_meter", data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({"some_meter": 0}, usage)

    def test_negative_and_other_values(self):
        """
        Tests that that transformer correctly handles a negative value
        mixed with non-zero values.
        """

        data = [
            {"timestamp": FAKE_DATA.t0, "volume": -1},
            {"timestamp": FAKE_DATA.t0_30, "volume": 25},
            {"timestamp": FAKE_DATA.t1, "volume": 27},
        ]

        xform = get_transformer(self.transformer_name)
        usage = xform.transform_usage("some_meter", data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({"some_meter": 1}, usage)


@mock.patch.object(general, 'get_transformer_config', lambda *args, **kwargs: {})
class TestMaxTransformer(base.DistilTestCase):
    def test_all_different_values(self):
        """
        Tests that the transformer correctly grabs the highest value,
        when all values are different.
        """

        data = [
            {'timestamp': FAKE_DATA.t0.isoformat(), 'volume': 12},
            {'timestamp': FAKE_DATA.t0_10.isoformat(), 'volume': 3},
            {'timestamp': FAKE_DATA.t0_20.isoformat(), 'volume': 7},
            {'timestamp': FAKE_DATA.t0_30.isoformat(), 'volume': 3},
            {'timestamp': FAKE_DATA.t0_40.isoformat(), 'volume': 25},
            {'timestamp': FAKE_DATA.t0_50.isoformat(), 'volume': 2},
            {'timestamp': FAKE_DATA.t1.isoformat(), 'volume': 6},
        ]

        xform = get_transformer('max')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'some_meter': 25}, usage)

    def test_all_same_values(self):
        """
        Tests that that transformer correctly grabs any value,
        when all values are the same.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': 25},
            {'timestamp': FAKE_DATA.t0_30, 'volume': 25},
            {'timestamp': FAKE_DATA.t1, 'volume': 25},
        ]

        xform = get_transformer('max')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'some_meter': 25}, usage)

    def test_none_value(self):
        """
        Tests that that transformer correctly handles a None value.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': None},
        ]

        xform = get_transformer('max')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'some_meter': 0}, usage)

    def test_none_and_other_values(self):
        """
        Tests that that transformer correctly handles a None value.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': None},
            {'timestamp': FAKE_DATA.t0_30, 'volume': 25},
            {'timestamp': FAKE_DATA.t1, 'volume': 27},
        ]

        xform = get_transformer('max')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'some_meter': 27}, usage)


@mock.patch.object(general, 'get_transformer_config', lambda *args, **kwargs: {})
class TestBlockStorageMaxTransformer(base.DistilTestCase):
    def test_all_different_values(self):
        """
        Tests that the transformer correctly grabs the highest value,
        when all values are different.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': 12,
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_10, 'volume': 3,
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_20, 'volume': 7,
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_30, 'volume': 3,
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_40, 'volume': 25,
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_50, 'volume': 2,
             'metadata': {}},
            {'timestamp': FAKE_DATA.t1, 'volume': 6,
             'metadata': {}},
        ]

        xform = get_transformer('storagemax')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'some_meter': 25}, usage)

    def test_all_same_values(self):
        """
        Tests that that transformer correctly grabs any value,
        when all values are the same.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': 25,
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_30, 'volume': 25,
             'metadata': {}},
            {'timestamp': FAKE_DATA.t1, 'volume': 25,
             'metadata': {}},
        ]

        xform = get_transformer('storagemax')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'some_meter': 25}, usage)

    def test_none_value(self):
        """
        Tests that that transformer correctly handles a None value.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': None,
             'metadata': {}},
        ]

        xform = get_transformer('storagemax')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'some_meter': 0}, usage)

    def test_none_and_other_values(self):
        """
        Tests that that transformer correctly handles a None value.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': None,
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_30, 'volume': 25,
             'metadata': {}},
            {'timestamp': FAKE_DATA.t1, 'volume': 27,
             'metadata': {}},
        ]

        xform = get_transformer('storagemax')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'some_meter': 27}, usage)


@mock.patch.object(general, 'get_transformer_config', lambda *args, **kwargs: {})
class TestObjectStorageMaxTransformer(base.DistilTestCase):

    @mock.patch.object(
        openstack, 'get_container_policy', mock.Mock(return_value='test-policy'))
    def test_all_different_values(self):
        """
        Tests that the transformer correctly grabs the highest value,
        when all values are different.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': 12,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_10, 'volume': 3,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_20, 'volume': 7,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_30, 'volume': 3,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_40, 'volume': 25,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_50, 'volume': 2,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
            {'timestamp': FAKE_DATA.t1, 'volume': 6,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
        ]

        xform = get_transformer('objectstoragemax')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'test-policy': 25}, usage)

    @mock.patch.object(
        openstack, 'get_container_policy', mock.Mock(return_value='test-policy'))
    def test_all_same_values(self):
        """
        Tests that that transformer correctly grabs any value,
        when all values are the same.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': 25,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_30, 'volume': 25,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
            {'timestamp': FAKE_DATA.t1, 'volume': 25,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
        ]

        xform = get_transformer('objectstoragemax')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'test-policy': 25}, usage)

    @mock.patch.object(
        openstack, 'get_container_policy', mock.Mock(return_value='test-policy'))
    def test_none_value(self):
        """
        Tests that that transformer correctly handles a None value.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': None,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
        ]

        xform = get_transformer('objectstoragemax')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'test-policy': 0}, usage)

    @mock.patch.object(
        openstack, 'get_container_policy', mock.Mock(return_value=None))
    def test_none_and_other_values(self):
        """
        Tests that that transformer correctly handles a None value.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': None,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
            {'timestamp': FAKE_DATA.t0_30, 'volume': 25,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
            {'timestamp': FAKE_DATA.t1, 'volume': 27,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {}},
        ]

        xform = get_transformer('objectstoragemax')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'some_meter': 27}, usage)


@mock.patch.object(general, 'get_transformer_config', lambda *args, **kwargs: {})
class TestSumTransformer(base.DistilTestCase):
    def test_basic_sum(self):
        """
        Tests that the transformer correctly calculate the sum value.
        """

        data = [
            {'timestamp': '2014-01-01T00:00:00', 'volume': 1},
            {'timestamp': '2014-01-01T00:10:00', 'volume': 1},
            {'timestamp': '2014-01-01T01:00:00', 'volume': 1},
        ]

        xform = get_transformer('sum')
        usage = xform.transform_usage('fake_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'fake_meter': 2}, usage)

    def test_none_value(self):
        """
        Tests that that transformer correctly handles a None value.
        """

        data = [
            {'timestamp': FAKE_DATA.t0.isoformat(), 'volume': None},
        ]

        xform = get_transformer('sum')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'some_meter': 0}, usage)

    def test_none_and_other_values(self):
        """
        Tests that that transformer correctly handles a None value.
        """

        data = [
            {'timestamp': FAKE_DATA.t0.isoformat(), 'volume': None},
            {'timestamp': FAKE_DATA.t0_30.isoformat(), 'volume': 25},
            {'timestamp': FAKE_DATA.t0_50.isoformat(), 'volume': 25},
        ]

        xform = get_transformer('sum')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'some_meter': 50}, usage)


@mock.patch.object(general, 'get_transformer_config', lambda *args, **kwargs: {})
class TestDatabaseVolumeMaxTransformer(base.DistilTestCase):

    @mock.patch.object(
        openstack, 'get_volume_type_for_volume',
        mock.Mock(return_value='b1.nvme1000'))
    def test_all_different_values(self):
        """
        Tests that the transformer correctly grabs the highest value,
        when all values are different.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '24', 'volume_id': 'vol_id'}},
            {'timestamp': FAKE_DATA.t0_10, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '13', 'volume_id': 'vol_id'}},
            {'timestamp': FAKE_DATA.t0_20, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '7', 'volume_id': 'vol_id'}},
            {'timestamp': FAKE_DATA.t0_30, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '13', 'volume_id': 'vol_id'}},
            {'timestamp': FAKE_DATA.t0_40, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '3', 'volume_id': 'vol_id'}},
            {'timestamp': FAKE_DATA.t0_50, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '25', 'volume_id': 'vol_id'}},
            {'timestamp': FAKE_DATA.t1, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '13', 'volume_id': 'vol_id'}},
        ]

        xform = get_transformer('databasevolumemax')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'b1.nvme1000': 25}, usage)

    @mock.patch.object(
        openstack, 'get_volume_type_for_volume',
        mock.Mock(return_value='b1.nvme1000'))
    def test_all_different_values(self):
        """
        Tests that the transformer tolerates a floating point value
        being found in the resource metadata.
        """

        data = [
            {'timestamp': FAKE_DATA.t0, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '24', 'volume_id': 'vol_id'}},
            {'timestamp': FAKE_DATA.t0_10, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '13', 'volume_id': 'vol_id'}},
            {'timestamp': FAKE_DATA.t0_20, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '7', 'volume_id': 'vol_id'}},
            {'timestamp': FAKE_DATA.t0_30, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '13', 'volume_id': 'vol_id'}},
            {'timestamp': FAKE_DATA.t0_40, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '3', 'volume_id': 'vol_id'}},
            {'timestamp': FAKE_DATA.t0_50, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '25.5', 'volume_id': 'vol_id'}},
            {'timestamp': FAKE_DATA.t1, 'volume': 1,
             'resource_id': '55d37509be3142de963caf82a9c7c447/stuff',
             'project_id': '55d37509be3142de963caf82a9c7c447',
             'metadata': {'volume.size': '13', 'volume_id': 'vol_id'}},
        ]

        xform = get_transformer('databasevolumemax')
        usage = xform.transform_usage('some_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'b1.nvme1000': 25}, usage)
