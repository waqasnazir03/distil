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

import mock

from distil.service.api.v2 import invoices
from distil.tests.unit import base


class InvoicesTest(base.DistilWithDbTestCase):
    @mock.patch('distil.common.general.convert_project_and_range')
    @mock.patch('distil.erp.drivers.odoo.OdooDriver.get_invoices')
    @mock.patch("distil.erp.drivers.odoo.client.Client")
    def test_get_invoices(
        self,
        mock_odoo_client,
        mock_get_invoices,
        mock_convert,
    ):
        class Project(object):
            def __init__(self, id, name):
                self.id = id
                self.name = name

        start = datetime.utcnow()
        end = datetime.utcnow()
        mock_convert.return_value = (
            Project('123', 'fake_project'), start, end
        )

        invoices.get_invoices('123', str(start), str(end))

        mock_get_invoices.assert_called_once_with(
            start, end, '123', detailed=False
        )
