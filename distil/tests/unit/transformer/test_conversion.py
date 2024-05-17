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
    t0_30 = p('2014-01-01T00:30:00')
    t1 = p('2014-01-01T01:00:00')

    # and one outside the window
    tpre = p('2013-12-31T23:50:00')

    flavor = 'c1.c1r1'
    flavor2 = 'c1.c2r2'


FAKE_CONFIG = {
    "uptime": {
        "tracked_states": ["active", "building", "paused", "rescued",
                           "resized"]
    },
    "fromimage": {
        "service": "volume.size",
        "md_keys": ["image_ref", "image_meta.base_image_ref"],
        "none_values": ["None", ""],
        "size_keys": ["root_gb"]
    },
    "databasemanagementuptime": {
        "prefix": "db.",
        "tracked_states": ["ACTIVE", "UPGRADE"],
    }
}


def fake_get_transformer_config(name):
    return FAKE_CONFIG.get(name, {})


@mock.patch.object(general, 'get_transformer_config',
                   fake_get_transformer_config)
class TestUpTimeTransformer(base.DistilTestCase):
    def test_trivial_run(self):
        """
        Test that an no input data produces empty uptime.
        """
        state = []

        xform = get_transformer('uptime')
        result = xform.transform_usage('state', state, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        self.assertEqual({}, result)

    def test_online_constant_flavor(self):
        """
        Test that a machine online for a 1h period with constant
        flavor works and gives 1h of uptime.
        """
        state = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor,
                          'status': 'active'}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor,
                          'status': 'active'}}
        ]

        xform = get_transformer('uptime')
        result = xform.transform_usage('state', state, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        self.assertEqual({FAKE_DATA.flavor: 3600}, result)

    def test_offline_constant_flavor(self):
        """
        Test that a machine offline for a 1h period with constant flavor
        works and gives zero uptime.
        """

        state = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor,
                          'status': 'stopped'}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor,
                          'status': 'stopped'}}
        ]

        xform = get_transformer('uptime')
        result = xform.transform_usage('state', state, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        self.assertEqual({}, result)

    def test_shutdown_during_period(self):
        """
        Test that a machine run for 0.5 then shutdown gives 0.5h uptime.
        """
        state = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor,
                          'status': 'active'}},
            {'timestamp': FAKE_DATA.t0_30.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor,
                          'status': 'stopped'}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor,
                          'status': 'stopped'}}
        ]

        xform = get_transformer('uptime')
        result = xform.transform_usage('state', state, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        self.assertEqual({FAKE_DATA.flavor: 3600}, result)

    def test_online_flavor_change(self):
        """
        Test that a machine run for 0.5h as m1.tiny, resized to m1.large,
        and run for a further 0.5 yields 0.5h of uptime in each class.
        """
        state = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor,
                          'status': 'active'}},
            {'timestamp': FAKE_DATA.t0_30.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor2,
                          'status': 'active'}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor2,
                          'status': 'active'}}
        ]

        xform = get_transformer('uptime')
        result = xform.transform_usage('state', state, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        self.assertDictEqual(
            {FAKE_DATA.flavor: 1800, FAKE_DATA.flavor2: 1800},
            result
        )

    def test_notification_case(self):
        """
        Test that the transformer handles the notification metedata key,
        if/when it can't find the status key.
        """
        state = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor,
                          'state': 'active'}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor,
                          'state': 'active'}}
        ]

        xform = get_transformer('uptime')
        result = xform.transform_usage('state', state, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        self.assertEqual({FAKE_DATA.flavor: 3600}, result)

    def test_no_state_in_metedata(self):
        """
        Test that the transformer doesn't fall over if there isn't one of
        the two state/status key options in the metadata.
        """
        state = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor}}
        ]

        xform = get_transformer('uptime')
        result = xform.transform_usage('state', state, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        self.assertEqual({}, result)

    def test_run_less_than_interval(self):
        """
        Test that an instance that has been running for less than the interval
        has full usage reported by the transformer.
        """
        entries = [
            {'timestamp': FAKE_DATA.t0_10.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor,
                          'status': 'active'}},
            {'timestamp': FAKE_DATA.t0_30.isoformat(),
             'metadata': {'instance_type': FAKE_DATA.flavor,
                          'status': 'active'}}
        ]

        xform = get_transformer('uptime')
        result = xform.transform_usage(
            'instance',
            entries,
            FAKE_DATA.t0,
            FAKE_DATA.t1
        )

        self.assertEqual({FAKE_DATA.flavor: 3600}, result)


@mock.patch.object(general, 'get_transformer_config',
                   fake_get_transformer_config)
class TestFromImageTransformer(base.DistilTestCase):
    """
    These tests rely on config settings for from_image,
    as defined in test constants, or in conf.yaml
    """

    def test_from_volume_case(self):
        """
        If instance is booted from volume transformer should return none.
        """
        data = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'image_ref': ""}},
            {'timestamp': FAKE_DATA.t0_30.isoformat(),
             'metadata': {'image_ref': "None"}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'image_ref': "None"}}
        ]

        data2 = [
            {'timestamp': FAKE_DATA.t0_30.isoformat(),
             'metadata': {'image_ref': "None"}}
        ]

        xform = get_transformer('fromimage')

        usage = xform.transform_usage('instance', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)
        usage2 = xform.transform_usage('instance', data2, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        self.assertIsNone(usage)
        self.assertIsNone(usage2)

    def test_default_to_from_volume_case(self):
        """
        Unless all image refs contain something, assume booted from volume.
        """
        data = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'image_ref': ""}},
            {'timestamp': FAKE_DATA.t0_30.isoformat(),
             'metadata': {'image_ref': "d5a4f118023928195f4ef"}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'image_ref': "None"}}
        ]

        xform = get_transformer('fromimage')
        usage = xform.transform_usage('instance', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertIsNone(usage)

    def test_from_image_case(self):
        """
        If all image refs contain something, should return entry.
        """
        data = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'image_ref': "d5a4f118023928195f4ef",
                          'root_gb': "20"}},
            {'timestamp': FAKE_DATA.t0_30.isoformat(),
             'metadata': {'image_ref': "d5a4f118023928195f4ef",
                          'root_gb': "20"}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'image_ref': "d5a4f118023928195f4ef",
                          'root_gb': "20"}}
        ]

        xform = get_transformer('fromimage')
        usage = xform.transform_usage('instance', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'volume.size': 20}, usage)

    def test_from_image_case_highest_size(self):
        """
        If all image refs contain something,
        should return entry with highest size from data.
        """
        data = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'image_ref': "d5a4f118023928195f4ef",
                          'root_gb': "20"}},
            {'timestamp': FAKE_DATA.t0_30.isoformat(),
             'metadata': {'image_ref': "d5a4f118023928195f4ef",
                          'root_gb': "60"}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'image_ref': "d5a4f118023928195f4ef",
                          'root_gb': "20"}}
        ]

        xform = get_transformer('fromimage')
        usage = xform.transform_usage('instance', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'volume.size': 60}, usage)


@mock.patch.object(general, 'get_transformer_config',
                   fake_get_transformer_config)
class TestNetworkServiceTransformer(base.DistilTestCase):
    def test_basic_sum(self):
        """Tests that the transformer correctly calculate the sum value.
        """

        data = [
            {'timestamp': '2014-01-01T00:00:00', 'volume': 1},
            {'timestamp': '2014-01-01T00:10:00', 'volume': 0},
            {'timestamp': '2014-01-01T01:00:00', 'volume': 2},
        ]

        xform = get_transformer('networkservice')
        usage = xform.transform_usage('fake_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'fake_meter': 1}, usage)

    def test_only_pending_service(self):
        """Tests that the transformer correctly calculate the sum value.
        """

        data = [
            {'timestamp': '2014-01-01T00:00:00', 'volume': 2},
            {'timestamp': '2014-01-01T00:10:00', 'volume': 2},
            {'timestamp': '2014-01-01T01:00:00', 'volume': 2},
        ]

        xform = get_transformer('networkservice')
        usage = xform.transform_usage('fake_meter', data, FAKE_DATA.t0,
                                      FAKE_DATA.t1)

        self.assertEqual({'fake_meter': 0}, usage)


@mock.patch.object(general, 'get_transformer_config',
                   fake_get_transformer_config)
class TestDatabaseManagementUpTimeTransformer(base.DistilTestCase):

    @mock.patch.object(
        openstack, 'get_flavor_name',
        mock.Mock(return_value=FAKE_DATA.flavor))
    def test_online_constant_flavor(self):
        """
        Test that a machine online for a 1h period with constant
        flavor works and gives 1h of uptime.
        """
        state = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor,
                          'status': 'ACTIVE'}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor,
                          'status': 'ACTIVE'}}
        ]

        xform = get_transformer('databasemanagementuptime')
        result = xform.transform_usage('state', state, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        management_service = (
            FAKE_CONFIG['databasemanagementuptime']['prefix'] + FAKE_DATA.flavor
        )

        self.assertEqual({management_service: 3600}, result)

    @mock.patch.object(
        openstack, 'get_flavor_name',
        mock.Mock(return_value=FAKE_DATA.flavor))
    def test_offline_constant_flavor(self):
        """
        Test that a machine in SHUTDOWN state for a 1h period gives 0h uptime,
        due to the SHUTDOWN state not being in the list of tracked states.
        """
        state = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor,
                          'status': 'SHUTDOWN'}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor,
                          'status': 'SHUTDOWN'}},
        ]

        xform = get_transformer('databasemanagementuptime')
        result = xform.transform_usage('state', state, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        self.assertEqual({}, result)

    @mock.patch.object(
        openstack, 'get_flavor_name',
        mock.Mock(return_value=FAKE_DATA.flavor))
    def test_shutdown_during_period(self):
        """
        Test that a machine run for 0.5 then shutdown gives 1h uptime.
        """
        state = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor,
                          'status': 'ACTIVE'}},
            {'timestamp': FAKE_DATA.t0_30.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor,
                          'status': 'SHUTDOWN'}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor,
                          'status': 'SHUTDOWN'}}
        ]

        xform = get_transformer('databasemanagementuptime')
        result = xform.transform_usage('state', state, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        management_service = (
            FAKE_CONFIG['databasemanagementuptime']['prefix'] + FAKE_DATA.flavor
        )

        self.assertEqual({management_service: 3600}, result)

    def test_online_flavor_change(self):
        """
        Test that a machine run for 10 minutes as one flavour, resized to another,
        and run for a further 50 minutes yields 0.5h of uptime in each class.
        """
        state = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor,
                          'status': 'ACTIVE'}},
            {'timestamp': FAKE_DATA.t0_10.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor2,
                          'status': 'ACTIVE'}},
            {'timestamp': FAKE_DATA.t0_30.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor2,
                          'status': 'ACTIVE'}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor2,
                          'status': 'ACTIVE'}}
        ]

        xform = get_transformer('databasemanagementuptime')

        def fake_get_flavor(name):
            return name

        with mock.patch.object(
                openstack, 'get_flavor_name', fake_get_flavor):
            result = xform.transform_usage(
                'state', state, FAKE_DATA.t0, FAKE_DATA.t1)

        management_service1 = (
            FAKE_CONFIG['databasemanagementuptime']['prefix'] + FAKE_DATA.flavor
        )
        management_service2 = (
            FAKE_CONFIG['databasemanagementuptime']['prefix'] + FAKE_DATA.flavor2
        )

        self.assertDictEqual(
            {management_service1: 1800, management_service2: 1800},
            result
        )

    @mock.patch.object(
        openstack, 'get_flavor_name',
        mock.Mock(return_value=FAKE_DATA.flavor))
    def test_no_state_in_metedata(self):
        """
        Test that the transformer doesn't fall over if there isn't one of
        the two state/status key options in the metadata.
        """
        state = [
            {'timestamp': FAKE_DATA.t0.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor}},
            {'timestamp': FAKE_DATA.t1.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor}}
        ]

        xform = get_transformer('databasemanagementuptime')
        result = xform.transform_usage('state', state, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        self.assertEqual({}, result)

    @mock.patch.object(
        openstack, 'get_flavor_name',
        mock.Mock(return_value=FAKE_DATA.flavor))
    def test_run_less_than_interval(self):
        """
        Test that an instance that has been running for less than the interval
        has full usage reported by the transformer.
        """
        state = [
            {'timestamp': FAKE_DATA.t0_10.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor,
                          'status': 'ACTIVE'}},
            {'timestamp': FAKE_DATA.t0_30.isoformat(),
             'metadata': {'flavor.id': FAKE_DATA.flavor,
                          'status': 'ACTIVE'}},
        ]

        xform = get_transformer('databasemanagementuptime')
        result = xform.transform_usage('state', state, FAKE_DATA.t0,
                                       FAKE_DATA.t1)

        management_service = (
            FAKE_CONFIG['databasemanagementuptime']['prefix'] + FAKE_DATA.flavor
        )

        self.assertEqual({management_service: 3600}, result)
