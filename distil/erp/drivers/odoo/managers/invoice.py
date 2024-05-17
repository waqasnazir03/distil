# Copyright (c) 2024 Catalyst Cloud Ltd.
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

from packaging.version import Version

from distil.erp.drivers.odoo.managers import base

ODOO_13_FIELDS = {
    # Key is latest, value is Odoo 13 equivalent.
    "move_type": "type",
    "is_move_sent": "invoice_sent",
    "payment_state": "invoice_payment_state",
}


class Invoice(base.RecordBase):
    def __init__(self, odoo, obj):
        # NOTE(callumdickinson): Explicitly define attributes,
        # to make them visible when using IDE or static type checking tools,
        # but also ensure they raise `AttributeError` when not selected
        # by the user in queries.
        # Since we still need to support Python 2.7 (for now),
        # we cannot use dataclasses or other more modern ways of doing this.
        if "amount_total" in obj:
            self.amount_total = obj.pop("amount_total")
            """Total (taxed) amount charged on the invoice."""
        if "amount_untaxed" in obj:
            self.amount_untaxed = obj.pop("amount_untaxed")
            """Total (untaxed) amount charged on the invoice."""
        if "id" in obj:
            self.id = obj.pop("id")
            """Invoice ID."""
        if "invoice_date" in obj:
            self.invoice_date = obj.pop("invoice_date")
            """Date associated with the invoice."""
        if "invoice_line_ids" in obj:
            self.invoice_line_ids = obj.pop("invoice_line_ids")
            """The list of IDs of the invoice lines that
            comprise this invoice.
            """
        if "move_type" in obj:
            self.move_type = obj.pop("move_type")
            """The type of invoice."""
        if "os_project" in obj:
            self.os_project = obj.pop("os_project")
            """The OpenStack project this invoice was generated for."""
        if "payment_state" in obj:
            self.payment_state = obj.pop("payment_state")
            """The current payment state of the invoice."""
        super(Invoice, self).__init__(odoo, obj)


class InvoiceManager(base.RecordManagerBase):
    def __init__(self, odoo):
        super(InvoiceManager, self).__init__(
            odoo=odoo,
            env=odoo.env["account.move"],
            record_class=Invoice,
        )
        if self._odoo_version < Version("14.0"):
            self._remote_fields = ODOO_13_FIELDS
        else:
            self._remote_fields = {}
        self._local_fields = {
            value: key
            for key, value in self._remote_fields.iteritems()
        }

    def _get_remote_field(self, attr):
        return self._remote_fields.get(attr, attr)

    def _get_local_field(self, attr):
        return self._local_fields.get(attr, attr)
