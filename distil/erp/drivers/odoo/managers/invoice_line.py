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

from distil.erp.drivers.odoo.managers import base


class InvoiceLine(base.RecordBase):
    def __init__(self, odoo, obj):
        # NOTE(callumdickinson): Explicitly define attributes,
        # to make them visible when using IDE or static type checking tools,
        # but also ensure they raise `AttributeError` when not selected
        # by the user in queries.
        # Since we still need to support Python 2.7 (for now),
        # we cannot use dataclasses or other more modern ways of doing this.
        if "id" in obj:
            self.id = obj.pop("id")
            """Invoice line ID."""
        if "line_tax_amount" in obj:
            self.line_tax_amount = obj.pop("line_tax_amount")
            """Amount charged in tax on the invoice line."""
        if "name" in obj:
            self.name = obj.pop("name")
            """Name of the product charged on the invoice line."""
        if "price_subtotal" in obj:
            self.price_subtotal = obj.pop("price_subtotal")
            """Amount charged for the product (untaxed)
            on the invoice line.
            """
        if "price_unit" in obj:
            self.price_unit = obj.pop("price_unit")
            """Unit price for the product used on the invoice line."""
        if "product_id" in obj:
            self.product_id = obj.pop("product_id")
            """ID of the product charged on the invoice line."""
        if "quantity" in obj:
            self.quantity = obj.pop("quantity")
            """Quantity of product charged on the invoice line."""
        super(InvoiceLine, self).__init__(odoo, obj)


class InvoiceLineManager(base.RecordManagerBase):
    def __init__(self, odoo):
        super(InvoiceLineManager, self).__init__(
            odoo=odoo,
            env=odoo.env["account.move.line"],
            record_class=InvoiceLine,
        )
