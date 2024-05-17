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

from collections import defaultdict, namedtuple
from datetime import datetime
from decimal import Decimal
import mock
import copy

import testscenarios.testcase

import mock_odoo_invoice_details as mock_invoices

from distil.erp.drivers import odoo
from distil.tests.unit import base

REGION = namedtuple('Region', ['id'])

PRODUCTS = [
    {
        'id': 1,
        'categ_id': [1, 'All products (.NET) / nz_1 / Compute'],
        'display_name': '[hour] NZ-1.c1.c1r1',
        'list_price': 0.00015,
        'default_code': 'hour',
        'description': '1 CPU, 1GB RAM'
    },
    {
        'id': 2,
        'categ_id': [2, 'All products (.NET) / nz_1 / Network'],
        'display_name': '[hour] NZ-1.n1.router',
        'list_price': 0.00025,
        'default_code': 'hour',
        'description': 'Router'
    },
    {
        'id': 3,
        'categ_id': [1, 'All products (.NET) / nz_1 / Block Storage'],
        'display_name': '[hour] NZ-1.b1.volume',
        'list_price': 0.00035,
        'default_code': 'hour',
        'description': 'Block storage'
    }
]


class TestOdooDriver(
    testscenarios.testcase.WithScenarios,
    base.DistilTestCase,
):
    scenarios = [
        (
            "odoo-13",
            {
                "odoo_version": "13.0",
                "account_move_fields": {
                    # Key is latest, value is Odoo 13 equivalent.
                    "move_type": "type",
                    "is_move_sent": "invoice_sent",
                    "payment_state": "invoice_payment_state",
                },
            },
        ),
        ("odoo-14", {"odoo_version": "14.0", "account_move_fields": {}}),
    ]

    config_file = 'distil.conf'

    def get_account_move_field(self, name):
        return self.account_move_fields.get(name, name)

    @mock.patch('odoorpc.ODOO')
    def test_get_products(self, mock_odoorpc):
        mock_odoo = mock.MagicMock(name="odoorpc.ODOO")
        mock_odoo.version = self.odoo_version
        mock_odoo.env = defaultdict(
            lambda: mock.MagicMock(name="odoorpc.ODOO.env"),
        )
        mock_odoo.env["product.product"].search.return_value = [
            str(product["id"]) for product in PRODUCTS
        ]
        mock_odoo.env["product.product"].read.side_effect = [PRODUCTS, []]
        mock_odoorpc.return_value = mock_odoo

        odoodriver = odoo.OdooDriver(self.conf)
        products = odoodriver.get_products(regions=['nz_1'])

        self.assertEqual(
            {
                'nz_1': {
                    'block storage': [{'description': 'Block storage',
                                       'rate': 0.00035,
                                       'name': 'b1.volume',
                                       'full_name': 'NZ-1.b1.volume',
                                       'unit': 'hour'}],
                    'compute': [{'description': '1 CPU, 1GB RAM',
                                 'rate': 0.00015,
                                 'name': 'c1.c1r1',
                                 'full_name': 'NZ-1.c1.c1r1',
                                 'unit': 'hour'}],
                    'network': [{'description': 'Router',
                                 'rate': 0.00025,
                                 'name': 'n1.router',
                                 'full_name': 'NZ-1.n1.router',
                                 'unit': 'hour'}]
                }
            },
            products
        )

    @mock.patch('odoorpc.ODOO')
    def test_get_invoices_without_details(self, mock_odoorpc):
        start = datetime(2017, 3, 1)
        end = datetime(2017, 9, 1)
        fake_project = '123'

        mock_odoo = mock.MagicMock(name="odoorpc.ODOO")
        mock_odoo.version = self.odoo_version
        mock_odoo.env = defaultdict(
            lambda: mock.MagicMock(name="odoorpc.ODOO.env"),
        )
        mock_odoo.env["account.move"].search.return_value = [
            '1',
            '2',
            '3',
            '4',
            '5',
            '6',
            '7',
        ]
        mock_odoo.env["account.move"].read.return_value = [
            # Invoice 1: Paid usage.
            {
                self.get_account_move_field("id"): 1,
                self.get_account_move_field("invoice_date"): '2017-03-31',
                self.get_account_move_field("move_type"): 'out_invoice',
                self.get_account_move_field("amount_untaxed"): 10,
                self.get_account_move_field("amount_total"): 11.5,
                self.get_account_move_field("payment_state"): 'paid',
            },
            # Invoice 2: Unpaid usage.
            {
                self.get_account_move_field("id"): 2,
                self.get_account_move_field("invoice_date"): '2017-04-30',
                self.get_account_move_field("move_type"): 'out_invoice',
                self.get_account_move_field("amount_untaxed"): 20,
                self.get_account_move_field("amount_total"): 23,
                self.get_account_move_field("payment_state"): 'not_paid',
            },
            # Invoice 3: Zero usage.
            {
                self.get_account_move_field("id"): 3,
                self.get_account_move_field("invoice_date"): '2017-05-31',
                self.get_account_move_field("move_type"): 'out_invoice',
                self.get_account_move_field("amount_untaxed"): 0,
                self.get_account_move_field("amount_total"): 0,
                self.get_account_move_field("payment_state"): 'paid',
            },
            # Invoice 4: Credit note.
            {
                self.get_account_move_field("id"): 4,
                self.get_account_move_field("invoice_date"): '2017-06-30',
                self.get_account_move_field("move_type"): 'out_refund',
                self.get_account_move_field("amount_untaxed"): 30,
                self.get_account_move_field("amount_total"): 34.5,
                self.get_account_move_field("payment_state"): 'paid',
            },
            # Invoice 5: Empty credit note.
            {
                self.get_account_move_field("id"): 5,
                self.get_account_move_field("invoice_date"): '2017-07-31',
                self.get_account_move_field("move_type"): 'out_refund',
                self.get_account_move_field("amount_untaxed"): 0,
                self.get_account_move_field("amount_total"): 0,
                self.get_account_move_field("payment_state"): 'paid',
            },
            # Invoice 6: Regular usage (that gets refunded by a credit note).
            {
                self.get_account_move_field("id"): 6,
                self.get_account_move_field("invoice_date"): '2017-08-31',
                self.get_account_move_field("move_type"): 'out_invoice',
                self.get_account_move_field("amount_untaxed"): 40,
                self.get_account_move_field("amount_total"): 46,
                self.get_account_move_field("payment_state"): 'paid',
            },
            # Invoice 7: Credit note that refunds invoice 6.
            {
                self.get_account_move_field("id"): 7,
                self.get_account_move_field("invoice_date"): '2017-08-31',
                self.get_account_move_field("move_type"): 'out_refund',
                self.get_account_move_field("amount_untaxed"): 40,
                self.get_account_move_field("amount_total"): 46,
                self.get_account_move_field("payment_state"): 'paid',
            },
        ]
        mock_odoorpc.return_value = mock_odoo

        odoodriver = odoo.OdooDriver(self.conf)
        invoices = odoodriver.get_invoices(start, end, fake_project)

        self.assertEqual(
            {
                '2017-03-31': {
                    'total_cost': 10,
                    'total_cost_taxed': 11.5,
                    'status': 'paid',
                },
                '2017-04-30': {
                    'total_cost': 20,
                    'total_cost_taxed': 23,
                    'status': 'not_paid',
                },
                '2017-05-31': {
                    'total_cost': 0,
                    'total_cost_taxed': 0,
                    'status': 'paid',
                },
                '2017-06-30': {
                    'total_cost': -30,
                    'total_cost_taxed': -34.5,
                    'status': 'paid',
                },
                '2017-07-31': {
                    'total_cost': 0,
                    'total_cost_taxed': 0,
                    'status': 'paid',
                },
                '2017-08-31': {
                    'total_cost': 0,
                    'total_cost_taxed': 0,
                    'status': 'paid',
                },
            },
            invoices
        )

    @mock.patch('odoorpc.ODOO')
    @mock.patch('distil.erp.drivers.odoo.OdooDriver.get_products')
    def test_get_invoices_with_details(self, mock_get_products, mock_odoorpc):
        start = datetime(2017, 3, 1)
        end = datetime(2017, 9, 1)
        fake_project = '123'

        mock_odoo = mock.MagicMock(name="odoorpc.ODOO")
        mock_odoo.version = self.odoo_version
        mock_odoo.env = defaultdict(
            lambda: mock.MagicMock(name="odoorpc.ODOO.env"),
        )
        mock_odoo.env["account.move"].search.return_value = [
            '1',
            '2',
            '3',
            '4',
            '5',
            '6',
            '7',
        ]
        mock_odoo.env["account.move"].read.side_effect = [
            # First call: Get invoice summaries.
            [
                # Invoice 1: Regular usage.
                {
                    self.get_account_move_field("id"): 1,
                    self.get_account_move_field("move_type"): 'out_invoice',
                    self.get_account_move_field("invoice_date"): '2017-03-31',
                    self.get_account_move_field("amount_untaxed"): 0.37,
                    self.get_account_move_field("amount_total"): 0.43,
                    self.get_account_move_field("payment_state"): 'paid',
                },
                # Invoice 2: Usage with a development grant and reseller discount.
                # On the Odoo side, this includes the reseller discount,
                # so the price output from it is cheaper than what is shown
                # on the dashboard.
                {
                    self.get_account_move_field("id"): 2,
                    self.get_account_move_field("move_type"): 'out_invoice',
                    self.get_account_move_field("invoice_date"): '2017-04-30',
                    self.get_account_move_field("amount_untaxed"): 4.19,
                    self.get_account_move_field("amount_total"): 4.82,
                    self.get_account_move_field("payment_state"): 'not_paid',
                },
                # Invoice 3: Zero usage.
                {
                    self.get_account_move_field("id"): 3,
                    self.get_account_move_field("move_type"): 'out_invoice',
                    self.get_account_move_field("invoice_date"): '2017-05-31',
                    self.get_account_move_field("amount_untaxed"): 0,
                    self.get_account_move_field("amount_total"): 0,
                    self.get_account_move_field("payment_state"): 'paid',
                },
                # Invoice 4: Credit note.
                {
                    self.get_account_move_field("id"): 4,
                    self.get_account_move_field("move_type"): 'out_refund',
                    self.get_account_move_field("invoice_date"): '2017-06-30',
                    self.get_account_move_field("amount_untaxed"): 0.12,
                    self.get_account_move_field("amount_total"): 0.14,
                    self.get_account_move_field("payment_state"): 'paid',
                },
                # Invoice 5: Empty credit note.
                {
                    self.get_account_move_field("id"): 5,
                    self.get_account_move_field("move_type"): 'out_refund',
                    self.get_account_move_field("invoice_date"): '2017-07-31',
                    self.get_account_move_field("amount_untaxed"): 0,
                    self.get_account_move_field("amount_total"): 0,
                    self.get_account_move_field("payment_state"): 'paid',
                },
                # Invoices 6 and 7 cover the same time period, with invoice 5
                # charging the customer an amount, and invoice 6 refunding it.
                # These should be merged into a single invoice by Distil,
                # with zeroed-out payment.
                {
                    self.get_account_move_field("id"): 6,
                    self.get_account_move_field("move_type"): 'out_invoice',
                    self.get_account_move_field("invoice_date"): '2017-08-31',
                    self.get_account_move_field("amount_untaxed"): 0.12,
                    self.get_account_move_field("amount_total"): 0.14,
                    self.get_account_move_field("payment_state"): 'paid',
                },
                {
                    self.get_account_move_field("id"): 7,
                    self.get_account_move_field("move_type"): 'out_refund',
                    self.get_account_move_field("invoice_date"): '2017-08-31',
                    self.get_account_move_field("amount_untaxed"): 0.12,
                    self.get_account_move_field("amount_total"): 0.14,
                    self.get_account_move_field("payment_state"): 'paid',
                },
            ],
            # Subsequent calls: Get invoice line IDs for each invoice.
            [{'id': 1, 'invoice_line_ids': [1, 2]}],
            [{'id': 2, 'invoice_line_ids': [3, 4]}],
            [{'id': 3, 'invoice_line_ids': []}],
            [{'id': 4, 'invoice_line_ids': [5]}],
            [{'id': 5, 'invoice_line_ids': []}],
            [{'id': 6, 'invoice_line_ids': [6]}],
            [{'id': 7, 'invoice_line_ids': [7]}],
        ]
        mock_odoo.env["account.move.line"].read.side_effect = [
            # Invoice 1: Regular usage.
            [
                {
                    'name': 'resource1',
                    'quantity': 1,
                    'price_unit': 0.123,
                    'price_subtotal': 0.12,
                    'line_tax_amount': 0.02,
                    'product_id': [1, '[hour] NZ-POR-1.c1.c2r8'],
                },
                {
                    'name': 'resource2',
                    'quantity': 2,
                    'price_unit': 0.123,
                    'price_subtotal': 0.25,
                    'line_tax_amount': 0.04,
                    'product_id': [1, '[hour] NZ-POR-1.c1.c2r8'],
                },
            ],
            # Invoice 2: Usage with a development grant and reseller discount.
            [
                {
                    'name': 'resource3',
                    'quantity': 3,
                    'price_unit': 0.123,
                    'price_subtotal': 0.37,
                    'line_tax_amount': 0.06,
                    'product_id': [1, '[hour] NZ-POR-1.c1.c2r8'],
                },
                {
                    'name': 'resource4',
                    'quantity': 40,
                    'price_unit': 0.123,
                    'price_subtotal': 4.92,
                    'line_tax_amount': 0.74,
                    'product_id': [1, '[hour] NZ-POR-1.c1.c2r8'],
                },
                {
                    'name': 'Development Grant',
                    'quantity': 1,
                    'price_unit': -0.1,
                    'price_subtotal': -0.1,
                    'line_tax_amount': -0.02,
                    'product_id': [4, 'cloud-dev-grant'],
                },
                {
                    'name': 'Reseller Margin discount',
                    'quantity': 1,
                    'price_unit': -1,
                    'price_subtotal': -1,
                    'line_tax_amount': -0.15,
                    'product_id': [8, 'reseller-margin-discount'],
                },
            ],
            # Invoice 3: Zero usage.
            [],
            # Invoice 4: Credit note.
            [
                {
                    'name': 'resource1',
                    'quantity': 1,
                    'price_unit': 0.123,
                    'price_subtotal': 0.12,
                    'line_tax_amount': 0.02,
                    'product_id': [1, '[hour] NZ-POR-1.c1.c2r8'],
                },
            ],
            # Invoice 5: Empty credit note.
            [],
            # Invoice 6: Regular usage (that gets refunded by a credit note).
            [
                {
                    'name': 'resource5',
                    'quantity': 1,
                    'price_unit': 0.123,
                    'price_subtotal': 0.12,
                    'line_tax_amount': 0.02,
                    'product_id': [1, '[hour] NZ-POR-1.c1.c2r8'],
                },
            ],
            # Invoice 7: Credit note that refunds invoice 5.
            [
                {
                    'name': 'resource5',
                    'quantity': 1,
                    'price_unit': 0.123,
                    'price_subtotal': 0.12,
                    'line_tax_amount': 0.02,
                    'product_id': [1, '[hour] NZ-POR-1.c1.c2r8'],
                },
            ],
        ]
        mock_odoorpc.return_value = mock_odoo

        odoodriver = odoo.OdooDriver(self.conf)
        odoodriver.product_unit_mapping = {1: 'hour'}
        odoodriver.product_category_mapping = {
            1: 'Compute',
            4: 'Discounts'
        }
        invoices = odoodriver.get_invoices(
            start, end, fake_project, detailed=True
        )

        # The category total price is get from odoo. The total price of
        # specific product is calculated based on invoice detail in odoo.
        self.assertEqual(
            {
                # Invoice 1: Regular usage.
                '2017-03-31': {
                    'total_cost': 0.37,
                    'total_cost_taxed': 0.43,
                    'status': 'paid',
                    'details': {
                        'Compute': {
                            'total_cost': 0.37,
                            'total_cost_taxed': 0.43,
                            'breakdown': {
                                'NZ-POR-1.c1.c2r8': [
                                    {
                                        'cost': 0.12,
                                        'cost_taxed': 0.14,
                                        'quantity': 1,
                                        'rate': 0.123,
                                        'resource_name': 'resource1',
                                        'unit': 'hour'
                                    },
                                    {
                                        'cost': 0.25,
                                        'cost_taxed': 0.29,
                                        'quantity': 2,
                                        'rate': 0.123,
                                        'resource_name': 'resource2',
                                        'unit': 'hour'
                                    },
                                ],
                            },
                        },
                    },
                },
                # Invoice 2: Usage with a development grant and reseller
                # discount.
                # On the Distil side, the reseller discount is hidden from
                # the user, so the full price is shown, excluding
                # the reseller discount.
                '2017-04-30': {
                    'total_cost': 5.19,
                    'total_cost_taxed': 5.97,
                    'status': 'not_paid',
                    'details': {
                        'Discounts': {
                            # The reseller margin discount (an invisible cost)
                            # is also charged in Odoo, but is excluded here
                            # by Distil.
                            'total_cost': -0.1,
                            'total_cost_taxed': -0.12,
                            'breakdown': {
                                'cloud-dev-grant': [
                                    {
                                        'quantity': 1.0,
                                        'unit': 'NZD',
                                        'cost': -0.1,
                                        'cost_taxed': -0.12,
                                        'resource_name': 'Development Grant',
                                        'rate': -0.1}
                                ],
                            },
                        },
                        'Compute': {
                            'total_cost': 5.29,
                            'total_cost_taxed': 6.09,
                            'breakdown': {
                                'NZ-POR-1.c1.c2r8': [
                                    {
                                        'cost': 0.37,
                                        'cost_taxed': 0.43,
                                        'quantity': 3.0,
                                        'rate': 0.123,
                                        'resource_name': 'resource3',
                                        'unit': 'hour'
                                    },
                                    {
                                        'cost': 4.92,
                                        'cost_taxed': 5.66,
                                        'quantity': 40,
                                        'rate': 0.123,
                                        'resource_name': 'resource4',
                                        'unit': 'hour'
                                    },
                                ],
                            },
                        },
                    },
                },
                # Invoice 3: Zero usage.
                '2017-05-31': {
                    'total_cost': 0,
                    'total_cost_taxed': 0,
                    'status': 'paid',
                    'details': {},
                },
                # Invoice 4: Credit note.
                '2017-06-30': {
                    'total_cost': -0.12,
                    'total_cost_taxed': -0.14,
                    'status': 'paid',
                    'details': {
                        'Compute': {
                            'total_cost': -0.12,
                            'total_cost_taxed': -0.14,
                            'breakdown': {
                                'NZ-POR-1.c1.c2r8': [
                                    {
                                        'cost': -0.12,
                                        'cost_taxed': -0.14,
                                        'quantity': -1,
                                        'rate': 0.123,
                                        'resource_name': 'resource1',
                                        'unit': 'hour'
                                    },
                                ],
                            },
                        },
                    },
                },
                # Invoice 5: Empty credit note.
                '2017-07-31': {
                    'total_cost': 0,
                    'total_cost_taxed': 0,
                    'status': 'paid',
                    'details': {},
                },
                # Invoices 6 and 7 merged together, with a total of zero cost.
                '2017-08-31': {
                    'total_cost': 0,
                    'total_cost_taxed': 0,
                    'status': 'paid',
                    'details': {
                        'Compute': {
                            'total_cost': 0,
                            'total_cost_taxed': 0,
                            'breakdown': {
                                'NZ-POR-1.c1.c2r8': [
                                    {
                                        'cost': 0.12,
                                        'cost_taxed': 0.14,
                                        'quantity': 1,
                                        'rate': 0.123,
                                        'resource_name': 'resource5',
                                        'unit': 'hour'
                                    },
                                    {
                                        'cost': -0.12,
                                        'cost_taxed': -0.14,
                                        'quantity': -1,
                                        'rate': 0.123,
                                        'resource_name': 'resource5',
                                        'unit': 'hour'
                                    },
                                ],
                            },
                        },
                    },
                },
            },
            invoices,
        )

    @mock.patch('odoorpc.ODOO')
    @mock.patch('distil.erp.drivers.odoo.OdooDriver.get_products')
    def test_get_quotations_without_details(self, mock_get_products,
                                            mock_odoorpc):
        mock_odoo = mock.MagicMock(name="odoorpc.ODOO")
        mock_odoo.version = self.odoo_version
        mock_odoorpc.return_value = mock_odoo

        mock_get_products.return_value = {
            'nz_1': {
                'Compute': [
                    {
                        'name': 'c1.c2r16', 'description': 'c1.c2r16',
                        'full_name': 'NZ-1.c1.c2r16',
                        'rate': 0.01, 'unit': 'hour'
                    }
                ],
                'Block Storage': [
                    {
                        'name': 'b1.standard', 'description': 'b1.standard',
                        'full_name': 'NZ-1.b1.standard',
                        'rate': 0.02, 'unit': 'gigabyte'
                    }
                ]
            }
        }

        class Resource(object):
            def __init__(self, id, info):
                self.id = id
                self.info = info

        resources = [
            Resource(1, '{"name": "", "type": "Volume"}'),
            Resource(2, '{"name": "", "type": "Virtual Machine"}')
        ]

        usage = [
            {
                'service': 'b1.standard',
                'resource_id': 1,
                'volume': 1024 * 1024 * 1024,
                'unit': 'byte',
            },
            {
                'service': 'c1.c2r16',
                'resource_id': 2,
                'volume': 3600,
                'unit': 'second',
            }
        ]

        odoodriver = odoo.OdooDriver(self.conf)
        quotations = odoodriver.get_quotations(
            'nz_1', 'fake_id', measurements=usage, resources=resources
        )

        self.assertEqual(
            {'total_cost': 0.03},
            quotations
        )

    @mock.patch('odoorpc.ODOO')
    @mock.patch('distil.erp.drivers.odoo.OdooDriver.get_products')
    def test_get_quotations_with_details(self, mock_get_products,
                                         mock_odoorpc):
        mock_odoo = mock.MagicMock(name="odoorpc.ODOO")
        mock_odoo.version = self.odoo_version
        mock_odoorpc.return_value = mock_odoo

        mock_get_products.return_value = {
            'nz_1': {
                'Compute': [
                    {
                        'name': 'c1.c2r16', 'description': 'c1.c2r16',
                        'full_name': 'NZ-1.c1.c2r16',
                        'rate': 0.01, 'unit': 'hour'
                    }
                ],
                'Block Storage': [
                    {
                        'name': 'b1.standard', 'description': 'b1.standard',
                        'full_name': 'NZ-1.b1.standard',
                        'rate': 0.02, 'unit': 'gigabyte'
                    }
                ]
            }
        }

        class Resource(object):
            def __init__(self, id, info):
                self.id = id
                self.info = info

        resources = [
            Resource(1, '{"name": "volume1", "type": "Volume"}'),
            Resource(2, '{"name": "instance2", "type": "Virtual Machine"}')
        ]

        usage = [
            {
                'service': 'b1.standard',
                'resource_id': 1,
                'volume': 1024 * 1024 * 1024,
                'unit': 'byte',
            },
            {
                'service': 'c1.c2r16',
                'resource_id': 2,
                'volume': 3600,
                'unit': 'second',
            }
        ]

        odoodriver = odoo.OdooDriver(self.conf)
        quotations = odoodriver.get_quotations(
            'nz_1', 'fake_id', measurements=usage, resources=resources,
            detailed=True
        )

        self.assertDictEqual(
            {
                'total_cost': 0.03,
                'details': {
                    'Compute': {
                        'total_cost': 0.01,
                        'breakdown': {
                            'NZ-1.c1.c2r16': [
                                {
                                    "resource_name": "instance2",
                                    "resource_id": 2,
                                    "cost": 0.01,
                                    "quantity": 1.0,
                                    "rate": 0.01,
                                    "unit": "hour",
                                }
                            ],
                        }
                    },
                    'Block Storage': {
                        'total_cost': 0.02,
                        'breakdown': {
                            'NZ-1.b1.standard': [
                                {
                                    "resource_name": "volume1",
                                    "resource_id": 1,
                                    "cost": 0.02,
                                    "quantity": 1.0,
                                    "rate": 0.02,
                                    "unit": "gigabyte",
                                }
                            ]
                        }
                    }
                }
            },
            quotations
        )

    @mock.patch('odoorpc.ODOO')
    @mock.patch('distil.erp.drivers.odoo.OdooDriver.get_products')
    def test_get_quotations_with_details_licensed_vm(self, mock_get_products,
                                                      mock_odoorpc):
        mock_odoo = mock.MagicMock(name="odoorpc.ODOO")
        mock_odoo.version = self.odoo_version
        mock_odoorpc.return_value = mock_odoo

        mock_get_products.return_value = {
            'nz_1': {
                'Compute': [
                    {
                        'name': 'c1.c2r16', 'description': 'c1.c2r16',
                        'full_name': 'NZ-1.c1.c2r16',
                        'rate': 0.01, 'unit': 'hour'
                    },
                    {
                        'name': 'c1.c4r32', 'description': 'c1.c4r32',
                        'full_name': 'NZ-1.c1.c4r32',
                        'rate': 0.04, 'unit': 'hour'
                    },
                    {
                        'name': 'c1.c2r16-windows',
                        'full_name': 'NZ-1.c1.c2r16-windows',
                        'description': 'c1.c2r16-windows',
                        'rate': 0.02, 'unit': 'hour'
                    },
                    {
                        'name': 'c1.c4r32-sql-server-standard-windows',
                        'full_name': 'NZ-1.c1.c4r32-sql-server-standard-windows',
                        'description': 'c1.c4r32-sql-server-standard-windows',
                        'rate': 0.04, 'unit': 'hour'
                    }
                ],
                'Block Storage': [
                    {
                        'name': 'b1.standard', 'description': 'b1.standard',
                        'full_name': 'NZ-1.b1.standard',
                        'rate': 0.02, 'unit': 'gigabyte'
                    }
                ]
            }
        }

        class Resource(object):
            def __init__(self, id, info):
                self.id = id
                self.info = info

        resources = [
            Resource(1, '{"name": "volume1", "type": "Volume"}'),
            Resource(
                2,
                '{"name": "instance2", "type": "Virtual Machine", '
                '"os_distro": "windows"}'
            ),
            Resource(
                3,
                '{"name": "instance3", "type": "Virtual Machine", '
                '"os_distro": "sql-server-standard-windows"}'
            )
        ]

        class Usage(object):
            def __init__(self, service, resource_id, volume, unit):
                self.service = service
                self.resource_id = resource_id
                self.volume = volume
                self.unit = unit

            def get(self, attr):
                return getattr(self, attr)

        usage = [
            Usage('b1.standard', 1, 1024 * 1024 * 1024, 'byte'),
            Usage('c1.c2r16', 2, 3600, 'second'),
            Usage('c1.c4r32', 3, 3600, 'second'),
        ]

        odoodriver = odoo.OdooDriver(self.conf)
        quotations = odoodriver.get_quotations(
            'nz_1', 'fake_id', measurements=usage, resources=resources,
            detailed=True
        )

        self.assertDictEqual(
            {
                'total_cost': 0.13,
                'details': {
                    'Compute': {
                        'total_cost': 0.11,
                        'breakdown': {
                            'NZ-1.c1.c2r16': [
                                {
                                    "resource_name": "instance2",
                                    "resource_id": 2,
                                    "cost": 0.01,
                                    "quantity": 1.0,
                                    "rate": 0.01,
                                    "unit": "hour",
                                }
                            ],
                            'NZ-1.c1.c2r16-windows': [
                                {
                                    "resource_name": "instance2",
                                    "resource_id": 2,
                                    "cost": 0.02,
                                    "quantity": 1.0,
                                    "rate": 0.02,
                                    "unit": "hour",
                                }
                            ],
                            'NZ-1.c1.c4r32': [
                                {
                                    "resource_name": "instance3",
                                    "resource_id": 3,
                                    "cost": 0.04,
                                    "quantity": 1.0,
                                    "rate": 0.04,
                                    "unit": "hour",
                                }
                            ],
                            'NZ-1.c1.c4r32-sql-server-standard-windows': [
                                {
                                    "resource_name": "instance3",
                                    "resource_id": 3,
                                    "cost": 0.04,
                                    "quantity": 1.0,
                                    "rate": 0.04,
                                    "unit": "hour",
                                }
                            ],
                        }
                    },
                    'Block Storage': {
                        'total_cost': 0.02,
                        'breakdown': {
                            'NZ-1.b1.standard': [
                                {
                                    "resource_name": "volume1",
                                    "resource_id": 1,
                                    "cost": 0.02,
                                    "quantity": 1.0,
                                    "rate": 0.02,
                                    "unit": "gigabyte",
                                }
                            ]
                        }
                    }
                }
            },
            quotations
        )

    @mock.patch('odoorpc.ODOO')
    @mock.patch('distil.erp.drivers.odoo.OdooDriver.get_products')
    def test_get_quotations_with_details_ignore_products(self,
                                                         mock_get_products,
                                                         mock_odoorpc):
        mock_odoo = mock.MagicMock(name="odoorpc.ODOO")
        mock_odoo.version = self.odoo_version
        mock_odoorpc.return_value = mock_odoo

        mock_get_products.return_value = {
            'nz_1': {
                'Compute': [
                    {
                        'name': 'c1.c2r16', 'description': 'c1.c2r16',
                        'full_name': 'NZ-1.c1.c2r16',
                        'rate': 0.01, 'unit': 'hour'
                    },
                ],
                'Block Storage': [
                    {
                        'name': 'b1.standard', 'description': 'b1.standard',
                        'full_name': 'NZ-1.b1.standard',
                        'rate': 0.02, 'unit': 'gigabyte'
                    },
                ],
                'COE': [
                    {
                        'name': 'coe1.cluster', 'description': 'COE Cluster',
                        'full_name': 'NZ-1.coe1.cluster',
                        'rate': 0.2, 'unit': 'hour'
                    },
                    {
                        'name': 'coe1.worker', 'description': 'COE Worker',
                        'full_name': 'NZ-1.coe1.worker',
                        'rate': 0.05, 'unit': 'worker'
                    },
                ],
            },
        }

        class Resource(object):
            def __init__(self, id, info):
                self.id = id
                self.info = info

        resources = [
            Resource(1, '{"name": "volume1", "type": "Volume"}'),
            Resource(2, '{"name": "instance2", "type": "Virtual Machine"}')
        ]

        usage = [
            {
                'service': 'b1.standard',
                'resource_id': 1,
                'volume': 1024 * 1024 * 1024,
                'unit': 'byte',
            },
            {
                'service': 'c1.c2r16',
                'resource_id': 2,
                'volume': 3600,
                'unit': 'second',
            },
            {
                'service': 'coe1.cluster',
                'resource_id': 3,
                'volume': 1,
                'unit': 'hour',
            },
            {
                'service': 'coe1.worker',
                'resource_id': 3,
                'volume': 3,
                'unit': 'worker',
            },
        ]

        odoodriver = odoo.OdooDriver(self.conf)
        quotations = odoodriver.get_quotations(
            'nz_1', 'fake_id', measurements=usage, resources=resources,
            detailed=True
        )

        self.assertDictEqual(
            {
                'total_cost': 0.03,
                'details': {
                    'Compute': {
                        'total_cost': 0.01,
                        'breakdown': {
                            'NZ-1.c1.c2r16': [
                                {
                                    "resource_name": "instance2",
                                    "resource_id": 2,
                                    "cost": 0.01,
                                    "quantity": 1.0,
                                    "rate": 0.01,
                                    "unit": "hour",
                                }
                            ],
                        }
                    },
                    'Block Storage': {
                        'total_cost': 0.02,
                        'breakdown': {
                            'NZ-1.b1.standard': [
                                {
                                    "resource_name": "volume1",
                                    "resource_id": 1,
                                    "cost": 0.02,
                                    "quantity": 1.0,
                                    "rate": 0.02,
                                    "unit": "gigabyte",
                                }
                            ]
                        }
                    }
                }
            },
            quotations
        )

    @mock.patch('odoorpc.ODOO')
    def test_get_credits(self, mock_odoorpc):
        fake_credits = [{'create_uid': [182, 'OpenStack Testing'],
                         'initial_balance': 500.0,
                         'voucher_code': '3dd294588f15404f8d77bd97e653324b',
                         'credit_type': [1, 'Cloud Trial Credit'],
                         'name': '3dd294588f15404f8d77bd97e653324b',
                         '__last_update': '2017-05-26 02:16:38',
                         'current_balance': 500.0,
                         'cloud_tenant': [212,
                                          'openstack-dev.catalyst.net.nz'],
                         'write_uid': [98, 'OpenStack Billing'],
                         'expiry_date': '2017-11-24',
                         'write_date': '2017-05-26 02:16:38',
                         'id': 68, 'create_date': '2017-02-14 02:12:40',
                         'recurring': False, 'start_date': '2017-10-23',
                         'display_name': '3dd294588f15404f8d77bd97e653324b'}]

        mock_odoo = mock.MagicMock(name="odoorpc.ODOO")
        mock_odoo.version = self.odoo_version
        mock_odoo.env = defaultdict(
            lambda: mock.MagicMock(name="odoorpc.ODOO.env"),
        )
        mock_odoo.env["openstack.credit"].search.return_value = [
            str(credit["id"]) for credit in fake_credits
        ]
        mock_odoo.env["openstack.credit"].read.return_value = fake_credits
        mock_odoorpc.return_value = mock_odoo

        odoodriver = odoo.OdooDriver(self.conf)

        credits = odoodriver.get_credits('fake_project_id',
                                         datetime.now())
        self.assertEqual([{"code": "3dd294588f15404f8d77bd97e653324b",
                           "recurring": False,
                           "expiry_date": "2017-11-24",
                           "balance": 500,
                           "type": "Cloud Trial Credit",
                           "start_date": "2017-02-14 02:12:40"}],
                         credits)

    @mock.patch('odoorpc.ODOO')
    def test_merge_invoice_details(self, mock_odoorpc):
        mock_odoo = mock.MagicMock(name="odoorpc.ODOO")
        mock_odoo.version = self.odoo_version
        mock_odoorpc.return_value = mock_odoo

        odoodriver = odoo.OdooDriver(self.conf)

        existing_details = copy.deepcopy(mock_invoices.MOCK_INVOICE_MERGING_EXISTING_DETAILS)
        new_details = copy.deepcopy(mock_invoices.MOCK_INVOICE_MERGING_NEW_DETAILS)

        merged_details = odoodriver.merge_invoice_details(existing_details, new_details)
        self.assertDictEqual(
            merged_details,
            mock_invoices.MERGE_INVOICE_EXPECTED_RESULTS
        )

    @mock.patch('odoorpc.ODOO')
    def test_is_healthy(self, mock_odoorpc):
        mock_odoo = mock.MagicMock(name="odoorpc.ODOO")
        mock_odoo.version = self.odoo_version
        mock_odoo.db.list.return_value = ["A", "B"]
        mock_odoorpc.return_value = mock_odoo

        odoodriver = odoo.OdooDriver(self.conf)
        self.assertTrue(odoodriver.is_healthy())

    @mock.patch('odoorpc.ODOO')
    def test_is_healthy_false(self, mock_odoorpc):
        mock_odoo = mock.MagicMock(name="odoorpc.ODOO")
        mock_odoo.version = self.odoo_version
        mock_odoo.report.list.side_effect = Exception("Odoo Error!")
        mock_odoorpc.return_value = mock_odoo

        odoodriver = odoo.OdooDriver(self.conf)
        self.assertFalse(odoodriver.is_healthy())
