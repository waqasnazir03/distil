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


class Product(base.RecordBase):
    def __init__(self, odoo, obj):
        # NOTE(callumdickinson): Explicitly define attributes,
        # to make them visible when using IDE or static type checking tools,
        # but also ensure they raise `AttributeError` when not selected
        # by the user in queries.
        # Since we still need to support Python 2.7 (for now),
        # we cannot use dataclasses or other more modern ways of doing this.
        if "categ_id" in obj:
            self.categ_id = obj.pop("categ_id")
            """The ID of the category this product is under."""
        if "default_code" in obj:
            self.default_code = obj.pop("default_code")
            """The unit of this product.

            Referred to as the "Default Code" in Odoo.
            """
        if "description" in obj:
            self.description = obj.pop("description")
            """A short description of this product"""
        if "display_name" in obj:
            self.display_name = obj.pop("display_name")
            """The name of this product in OpenStack, and on invoices."""
        if "id" in obj:
            self.id = obj.pop("id")
            """Product ID."""
        if "list_price" in obj:
            self.list_price = obj.pop("list_price")
            """The list price of the product.

            This becomes the unit price of the product on invoices.
            """
        super(Product, self).__init__(odoo, obj)


class ProductManager(base.RecordManagerBase):
    def __init__(self, odoo):
        super(ProductManager, self).__init__(
            odoo=odoo,
            env=odoo.env["product.product"],
            record_class=Product,
        )
