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


class Credit(base.RecordBase):
    def __init__(self, odoo, obj):
        # NOTE(callumdickinson): Explicitly define attributes,
        # to make them visible when using IDE or static type checking tools,
        # but also ensure they raise `AttributeError` when not selected
        # by the user in queries.
        # Since we still need to support Python 2.7 (for now),
        # we cannot use dataclasses or other more modern ways of doing this.
        if "create_date" in obj:
            self.create_date = obj.pop("create_date")
            """Creation date of the credit."""
        if "credit_type" in obj:
            self.credit_type = obj.pop("credit_type")
            """Type of credit."""
        if "current_balance" in obj:
            self.current_balance = obj.pop("current_balance")
            """Current balance remaining to be used in the credit."""
        if "expiry_date" in obj:
            self.expiry_date = obj.pop("expiry_date")
            """Expiry date of the credit."""
        if "id" in obj:
            self.id = obj.pop("id")
            """Credit ID."""
        if "voucher_code" in obj:
            self.voucher_code = obj.pop("voucher_code")
            """Voucher code used when applying for the credit."""
        super(Credit, self).__init__(odoo, obj)


class CreditManager(base.RecordManagerBase):
    def __init__(self, odoo):
        super(CreditManager, self).__init__(
            odoo=odoo,
            env=odoo.env["openstack.credit"],
            record_class=Credit,
        )
