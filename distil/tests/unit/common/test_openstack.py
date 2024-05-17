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

import flask
import mock

from keystoneauth1.exceptions import NotFound

from distil import exceptions as ex
from distil.common import openstack
from distil.tests.unit import base


class TestOpenStack(base.DistilTestCase):

    @mock.patch('distil.common.openstack.get_keystone_client')
    def test_get_domain(self, ks_client_factory):
        ks_client = mock.MagicMock()
        ks_client_factory.return_value = ks_client

        ks_client.domains.get.side_effect = NotFound()
        ks_client.domains.list.return_value = ['domain_1']

        my_domain = openstack.get_domain("some_domain_id")
        ks_client.domains.get.assert_called_with("some_domain_id")
        ks_client.domains.list.assert_called_with(name="some_domain_id")
        self.assertEqual(my_domain, 'domain_1')

    @mock.patch('distil.common.openstack.get_keystone_client')
    def test_get_projects(self, ks_client_factory):
        ks_client = mock.MagicMock()
        ks_client_factory.return_value = ks_client

        project_1 = mock.MagicMock()
        project_1.to_dict.return_value = {'name': 'project_1'}
        domain_1 = mock.MagicMock(id="domain_id_1")

        ks_client.projects.list.return_value = [project_1]
        ks_client.domains.get.return_value = domain_1

        projects = openstack.get_projects()
        self.assertEqual([project_1.to_dict.return_value], projects)
        ks_client.domains.get.assert_not_called()
        ks_client.domains.list.assert_not_called()

        projects = openstack.get_projects(domains=['domain_1'])

        self.assertEqual([project_1.to_dict.return_value], projects)
        ks_client.domains.get.assert_called_with("domain_1")
        ks_client.projects.list.assert_called_with(domain=domain_1)
