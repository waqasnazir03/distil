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

import collections
import copy
from decimal import Decimal
import itertools
import json
import re

import odoorpc
from oslo_log import log

from distil.common import cache
from distil.common import constants
from distil.common import general
from distil.common import openstack
from distil.erp.drivers.odoo import client
from distil.erp import driver
from distil import exceptions

LOG = log.getLogger(__name__)

COMPUTE_CATEGORY = "Compute"
NETWORK_CATEGORY = "Network"
BLOCKSTORAGE_CATEGORY = "Block Storage"
OBJECTSTORAGE_CATEGORY = "Object Storage"
DISCOUNTS_CATEGORY = "Discounts"
PREMIUM_SUPPORT = "Premium Support"
SUPPORT = "Support"
SLA_DISCOUNT_CATEGORY = "SLA Discount"


class OdooDriver(driver.BaseDriver):
    def __init__(self, conf):
        self.PRODUCT_CATEGORY = [COMPUTE_CATEGORY, NETWORK_CATEGORY,
                                 BLOCKSTORAGE_CATEGORY,
                                 DISCOUNTS_CATEGORY, PREMIUM_SUPPORT, SUPPORT,
                                 SLA_DISCOUNT_CATEGORY] + \
            conf.odoo.extra_product_category_list

        self.odoo_client = client.Client(
            protocol=conf.odoo.protocol,
            hostname=conf.odoo.hostname,
            port=conf.odoo.port,
            version=conf.odoo.version,
            database=conf.odoo.database,
            username=conf.odoo.user,
            password=conf.odoo.password,
        )

        self.region_mapping = {}
        self.reverse_region_mapping = {}

        # NOTE(flwang): This is not necessary for most of cases, but just in
        # case some cloud providers are using different region name formats in
        # Keystone and Odoo.
        if conf.odoo.region_mapping:
            regions = conf.odoo.region_mapping.split(',')
            self.region_mapping = dict(
                [(r.split(":")[0].strip(),
                  r.split(":")[1].strip())
                 for r in regions]
            )
            self.reverse_region_mapping = dict(
                [(r.split(":")[1].strip(),
                  r.split(":")[0].strip())
                 for r in regions]
            )

        self.ignore_products_in_quotations = set(
            conf.odoo.ignore_products_in_quotations,
        )

        self.conf = conf

        self.product_category_mapping = {}
        self.product_unit_mapping = {}

    def is_healthy(self):
        try:
            # The odoo user not always has the permission to list db.
            # self.odoo_client.db.list()
            self.odoo_client.report.list()
            return True
        except Exception as e:
            LOG.exception(e)
            return False

    @cache.memoize
    def get_products(self, regions=[]):
        self.product_category_mapping.clear()
        self.product_unit_mapping.clear()
        odoo_regions = []

        if not regions:
            regions = [r.id for r in openstack.get_regions()]
        for r in regions:
            odoo_regions.append(self.region_mapping.get(r, r))

        LOG.debug('Get products for regions in Odoo: %s', odoo_regions)

        product_fields = [
            "categ_id",
            "display_name",
            "list_price",
            "default_code",
            "description",
        ]

        prices = {}
        try:
            # NOTE(flwang): Currently, the main bottle neck is the query of
            # odoo, so we prefer to get all the products by one call and then
            # filter them in Distil. And another problem is the filter for
            # region doesn't work when query odoo.
            categ_ids = self.odoo_client.env["product.category"].search(
                [("name", "in", self.PRODUCT_CATEGORY)],
            )
            products = self.odoo_client.product.list(
                [
                    ("categ_id", "in", categ_ids),
                    ("sale_ok", "=", True),
                    ("active", "=", True),
                ],
                fields=product_fields,
            )

            for region in odoo_regions:
                # Ensure returned region name is same with what user see from
                # Keystone.
                actual_region = self.reverse_region_mapping.get(region, region)
                prices[actual_region] = collections.defaultdict(list)

                for product in products:
                    category = product.categ_id[1].split('/')[-1].strip()
                    # NOTE(flwang): Always add the discount product into the
                    # mapping so that we can use it for /invoices API. But
                    # those product won't be returned as a part of the
                    # /products API.
                    self.product_category_mapping[product.id] = category
                    if category in (DISCOUNTS_CATEGORY, SLA_DISCOUNT_CATEGORY):
                        continue

                    if region.upper() not in product.display_name:
                        continue

                    name = re.sub(
                        r'.*%s\.' % region.upper(),
                        '',
                        product.display_name)
                    # TODO(callumdickinson): Useless, remove.
                    if 'pre-prod' in name:
                        continue

                    rate = round(product.list_price,
                                 constants.RATE_DIGITS)
                    # NOTE(flwang): default_code is Internal Reference on
                    # Odoo GUI
                    unit = product.default_code
                    desc = product.description
                    self.product_unit_mapping[product.id] = unit
                    full_name = re.sub(
                        r'\[%s\] ' % product.default_code,
                        '',
                        product.display_name)

                    prices[actual_region][category.lower()].append(
                        {
                            'name': name,
                            'full_name': full_name,
                            'rate': rate,
                            'unit': unit,
                            'description': desc
                        }
                    )

            # Handle object storage products
            categ_ids = self.odoo_client.env["product.category"].search(
                [("name", "=", OBJECTSTORAGE_CATEGORY)],
            )
            products = self.odoo_client.product.list(
                [
                    ("categ_id", "in", categ_ids),
                    ("sale_ok", "=", True),
                    ("active", "=", True),
                ],
                fields=product_fields,
            )

            for product in products:
                category = product.categ_id[1].split('/')[-1].strip()
                self.product_category_mapping[product.id] = category

                rate = round(product.list_price, constants.RATE_DIGITS)
                # NOTE(flwang): default_code is Internal Reference on
                # Odoo GUI
                unit = product.default_code
                desc = product.description
                self.product_unit_mapping[product.id] = unit

                product_dict = {
                    'name': product.display_name.lower(),
                    'full_name': product.display_name,
                    'rate': rate,
                    'unit': unit,
                    'description': desc
                }

                # add swift products to all regions
                for region in odoo_regions:
                    actual_region = self.reverse_region_mapping.get(
                        region, region)

                    prices[actual_region][category.lower()].append(
                        product_dict)
        except odoorpc.error.Error as e:
            LOG.exception(e)
            return {}

        return prices

    def _get_invoice_detail(self, invoice_id, is_refund=False):
        """Get invoice details.

        Three results will be returned:

          * `detail_dict`
          * `invisible_cost`
          * `invisible_cost_taxed`

        `invisible_cost` and invisible_cost_taxed` are the total costs
        of all products that cloud providers don't want to show
        in the invoice API, without and with tax, respectively.

        Invisible costs are positive when invisible charges are added,
        resulting in a lower shown total price.
        They can also be negative when invisible credits are added
        (e.g. reseller margin discounts), resulting in a
        higher shown total price.

        If `is_refund` is `True`, the invoice will be treated as
        a credit note, and all line items will be returned with
        a negative quantity and costs to reflect this.

        The format of detail_dict is as below:

        ```python
        {
          'category': {
            'total_cost': xxx,
            'breakdown': {
              '<product_name>': [
                {
                  'resource_name': '',
                  'quantity': '',
                  'unit': '',
                  'rate': '',
                  'cost': '',
                  'cost_taxed': '',
                }
              ],
              '<product_name>': [
                {
                  'resource_name': '',
                  'quantity': '',
                  'unit': '',
                  'rate': '',
                  'cost': '',
                  'cost_taxed': '',
                }
              ]
            }
          }
        }
        ```
        """
        # NOTE(flwang): To hide some cost like 'reseller_margin_discount', we
        # need to get the total amount for those cost/usage and then
        # re-calculate the total cost for the monthly cost.
        invisible_cost = 0
        invisible_cost_taxed = 0

        invoice = self.odoo_client.invoice.get(
            invoice_id,
            fields=["invoice_line_ids"],
        )[0]
        invoice_lines = self.odoo_client.invoice_line.get(
            invoice.invoice_line_ids,
            fields=[
                "product_id",
                "name",
                "quantity",
                "price_unit",
                "price_subtotal",
                "line_tax_amount",
            ],
        )

        # Automatically populate product category default values
        # when invoice lines are added for that category.
        detail_dict = collections.defaultdict(
            lambda: {
                'total_cost': 0,
                'total_cost_taxed': 0,
                'breakdown': collections.defaultdict(list),
            },
        )

        for line in invoice_lines:
            if not line.product_id:
                # NOTE(michaelball): expected case: "note/comment" lines in
                # Odoo (which are valid invoice lines but not products,
                # therefore have no product id)
                continue

            line_info = {
                'resource_name': line.name,
                'quantity': round(line.quantity, constants.QUANTITY_DIGITS),
                'rate': round(line.price_unit, constants.RATE_DIGITS),
                # TODO(flwang): We're not exposing some product at all, such
                # as the discount product. For those kind of product, using
                # NZD as the default. We may have to revisit this part later
                # if there is new requirement.
                'unit': self.product_unit_mapping.get(line.product_id[0],
                                                      'NZD'),
                'cost': round(line.price_subtotal, constants.PRICE_DIGITS),
                'cost_taxed': round(
                    line.price_subtotal + line.line_tax_amount,
                    constants.PRICE_DIGITS,
                ),
            }

            # Credit notes are stored as a separate type of invoice in Odoo,
            # with the quantity and cost being positive values.
            # Distil returns credits/refunds as negative-quantity
            # invoice lines, so ensure the values are negative
            # to reflect this.
            if is_refund:
                line_info['rate'] = abs(line_info['rate'])
                line_info['quantity'] = -abs(line_info['quantity'])
                line_info['cost'] = -abs(line_info['cost'])
                line_info['cost_taxed'] = -abs(line_info['cost_taxed'])

            product = line.product_id[1]
            if re.match(r"\[.+\].+", product):
                product = product.split(']')[1].strip()

            if product in self.conf.odoo.invisible_products:
                invisible_cost += line_info['cost']
                invisible_cost_taxed += line_info['cost_taxed']
            else:
                category = self.product_category_mapping[line.product_id[0]]

                detail_dict[category]['total_cost'] = round(
                    (detail_dict[category]['total_cost'] + line_info['cost']),
                    constants.PRICE_DIGITS
                )
                detail_dict[category]['total_cost_taxed'] = round(
                    (
                        detail_dict[category]['total_cost_taxed']
                        + line_info['cost_taxed']
                    ),
                    constants.PRICE_DIGITS
                )
                detail_dict[category]['breakdown'][product].append(line_info)

        return (detail_dict, invisible_cost, invisible_cost_taxed)

    def merge_invoice_details(self, details, merging_details):
        """merge_invoice_details is for when two invoices share the same date
        (ie. there's two invoices for the same month) and a detailed response
        is requested.
        If this is the case, then each region within the new set of details
        needs to be combined or added with the existing details for that date,
        and within each region the same needs to be done with resources.
        The expected format of a details section is:
            {
                "[region 1]": {
                    "total_cost": 1234.56,
                    "breakdown": {
                        "[resource 1]": [
                            {
                                "rate": 0.5,
                                "resource_name": "[resource name 1]",
                                "cost": 1.5,
                                "unit": "NZD",
                                "quantity": 3
                            },
                            ...
                        ],
                        "[resource 2]": [...]
                    },
                "[region 1]": {...}
            }
        """
        for region in merging_details:
            if region not in details:
                details[region] = merging_details[region]
                continue
            details[region]["total_cost"] += (
                merging_details[region]["total_cost"]
            )
            details[region]["total_cost_taxed"] += (
                merging_details[region]["total_cost_taxed"]
            )
            for resource in merging_details[region]['breakdown']:
                if resource not in details[region]['breakdown']:
                    details[region]['breakdown'][resource] = (
                        merging_details[region]['breakdown'][resource]
                    )
                    continue
                for line in merging_details[region]['breakdown'][resource]:
                    details[region]['breakdown'][resource].append(line)

        return details

    @cache.memoize
    def get_invoices(self, start, end, project_id, detailed=False):
        """Get history invoices from Odoo given a time range.

        Return value is in the following format:
        {
          '<billing_date1>': {
            'total_cost': 100,
            'details': {
                ...
            }
          },
          '<billing_date2>': {
            'total_cost': 200,
            'details': {
                ...
            }
          }
        }

        :param start: Start time, a datetime object.
        :param end: End time, a datetime object.
        :param project_id: project ID.
        :param detailed: Get detailed information.
        :return: The history invoices information for each month.
        """
        # Get invoices in time ascending order.
        result = collections.OrderedDict()

        try:
            odoo_project = self.odoo_client.project.list(
                [("os_id", "=", project_id)],
                as_ids=True,
            )

            if not odoo_project:
                LOG.debug('Project id not found in Odoo: "%s".' % (project_id))
                return result

            invoices = self.odoo_client.invoice.list(
                [
                    ("invoice_date", ">=", str(start.date())),
                    ("invoice_date", "<=", str(end.date())),
                    ("os_project", "=", odoo_project[0]),
                ],
                order="invoice_date",
                fields=[
                    "invoice_date",
                    "move_type",
                    "amount_untaxed",
                    "amount_total",
                    "payment_state",
                ],
            )

            if not invoices:
                LOG.debug('No history invoices returned from Odoo.')
                return result

            LOG.debug("Found invoices: %s", invoices)

            for v in invoices:
                # Credit notes are stored as a separate type of invoice
                # in Odoo, with the total cost being positive values.
                # Distil returns credit notes as negative-quantity invoices,
                # so invert the values to reflect this.
                if v.move_type == 'out_refund':
                    is_refund = True
                    v.amount_untaxed = -v.amount_untaxed
                    v.amount_total = -v.amount_total
                else:
                    is_refund = False

                # Merging occues when two invoices share the same date.
                # For non-detailed requests we simply combine the two invoice
                # values and assess whether all invoices are paid or not.
                # For detailed requests, we also merge those detailed
                # for each of the invoices with the given date
                merging = v.invoice_date in result

                if merging:
                    result[v.invoice_date]['total_cost'] += round(
                        v.amount_untaxed,
                        constants.PRICE_DIGITS,
                    )
                    result[v.invoice_date]['total_cost_taxed'] += round(
                        v.amount_total,
                        constants.PRICE_DIGITS,
                    )

                    # NOTE(michaelball): default status to "not_paid" if there
                    # is a discrepency, as the month's bills has not been paid
                    # in full. Otherwise we can leave it as is.
                    # Expected values are "paid" and "not_paid"
                    if result[v.invoice_date]["status"] != v.payment_state:
                        result[v.invoice_date]["status"] = "not_paid"
                else:
                    result[v.invoice_date] = {
                        'total_cost': round(
                            v.amount_untaxed,
                            constants.PRICE_DIGITS,
                        ),
                        'total_cost_taxed': round(
                            v.amount_total,
                            constants.PRICE_DIGITS,
                        ),
                        'status': v.payment_state
                    }

                if detailed:
                    # Populate product category mapping first. This should be
                    # quick since we cached get_products()
                    if not self.product_category_mapping:
                        self.get_products()

                    (
                        details,
                        invisible_cost,
                        invisible_cost_taxed,
                    ) = self._get_invoice_detail(
                        invoice_id=v.id,
                        is_refund=is_refund,
                    )
                    # NOTE(callumdickinson): Deduct the total cost
                    # based on the invisible cost.
                    # The invisible cost can be negative in some cases,
                    # for example, reseller margin discounts.
                    # This would result in a higher final price.
                    m = result[v.invoice_date]
                    m['total_cost'] = round(
                        m['total_cost'] - invisible_cost,
                        constants.PRICE_DIGITS,
                    )
                    m['total_cost_taxed'] = round(
                        m['total_cost_taxed'] - invisible_cost_taxed,
                        constants.PRICE_DIGITS,
                    )

                    if merging:
                        merged_details = self.merge_invoice_details(
                            m['details'], details
                        )
                        result[v.invoice_date].update(
                            {'details': merged_details}
                        )
                    else:
                        result[v.invoice_date].update({'details': details})
        except Exception as e:
            LOG.exception(
                'Error occurred when getting invoices from Odoo, '
                'error: %s' % str(e)
            )

            raise exceptions.ERPException(
                'Failed to get invoices from ERP server.'
            )

        return result

    @cache.memoize
    def _get_service_mapping(self, products):
        """Gets mapping from service name to service type.

        :param products: Product dict in a region returned from odoo.
        """
        srv_mapping = {}

        for category, p_list in products.items():
            for p in p_list:
                srv_mapping[p['name']] = category.title()

        return srv_mapping

    @cache.memoize
    def _get_service_price(self, service_name, service_type, products):
        """Get service price information from price definitions."""
        price = {'service_name': service_name}

        # NOTE(adriant): We do this to handle the object storage policy
        #                name to product translation
        formatted_name = service_name.lower().replace("--", ".")

        if service_type in products:
            for s in products[service_type]:
                if s['name'] == formatted_name:
                    price.update({
                        'rate': s['rate'], 'unit': s['unit'],
                        'product_name': s['full_name']})
                    break
        else:
            found = False
            for category, services in products.items():
                for s in services:
                    if s['name'] == formatted_name:
                        price.update({
                            'rate': s['rate'], 'unit': s['unit'],
                            'product_name': s['full_name']})
                        found = True
                        break

            if not found:
                for category, services in products.items():
                    for s in services:
                        # NOTE(adriant): this will find a partial match like:
                        #                  'o1.standard' in 'NZ.o1.standard'
                        if formatted_name in s['name']:
                            price.update({
                                'rate': s['rate'], 'unit': s['unit'],
                                'product_name': s['full_name']})
                            found = True
                            break

            if not found:
                raise exceptions.NotFoundException(
                    'Price not found, service name: %s, service type: %s' %
                    (formatted_name, service_type)
                )

        if 'unit' in price and not price['unit']:
            raise exceptions.ERPException(
                "Product: %s is missing 'unit' definition." %
                formatted_name
            )

        return price

    def _get_entry_info(self, entry, resources_info, service_mapping):
        service_name = entry.get('service')
        volume = entry.get('volume')
        unit = entry.get('unit')
        res_id = entry.get('resource_id')
        resource = resources_info.get(res_id, {})
        # resource_type is the type defined in meter_mappings.yml.
        resource_type = resource.get('type')
        service_type = service_mapping.get(service_name, resource_type)

        return (service_name, service_type, volume, unit, resource,
                resource_type)

    def get_quotations(self, region, project_id, measurements=[], resources=[],
                       detailed=False):
        """Get current month quotation.

        Return value is in the following format:
        {
          '<current_date>': {
            'total_cost': 100,
            'details': {
                'Compute': {
                    'total_cost': xxx,
                    'breakdown': {}
                }
            }
          }
        }

        :param region: Region name.
        :param project_id: Project ID.
        :param measurements: Current month usage collection.
        :param resources: List of resources.
        :param detailed: If get detailed information or not.
        :return: Current month quotation.
        """
        total_cost = 0
        price_mapping = {}
        cost_details = {}

        resources_info = {}
        for row in resources:
            info = json.loads(row.info)
            info.update({'id': row.id})
            resources_info[row.id] = info

        # NOTE(flwang): For most of the cases of Distil API, the request comes
        # from billing panel. Billing panel sends 1 API call for /invoices and
        # several API calls for /quotations against different regions. So it's
        # not efficient to specify the region for get_products method because
        # it won't help cache the products based on the parameters.
        products = self.get_products()[region]
        service_mapping = self._get_service_mapping(products)

        # Find licensed VM usage entries
        licensed_vm_entries = []
        for entry in measurements:
            (service_name, service_type, _, _, resource,
             resource_type) = self._get_entry_info(entry, resources_info,
                                                   service_mapping)

            for os_distro in self.conf.odoo.licensed_os_distro_list:
                if (service_type == COMPUTE_CATEGORY
                        and resource_type == 'Virtual Machine'
                        and resource.get('os_distro') == os_distro):
                    new_entry = copy.deepcopy(entry)
                    setattr(new_entry,
                            'service', '%s-%s' % (service_name, os_distro))
                    licensed_vm_entries.append(new_entry)

        for entry in itertools.chain(measurements, licensed_vm_entries):
            (service_name, service_type, volume, unit, resource,
             resource_type) = self._get_entry_info(entry, resources_info,
                                                   service_mapping)

            # NOTE(callumdickinson): Remove usage for products
            # that are on the 'ignored products' list.
            if service_name in self.ignore_products_in_quotations:
                continue

            res_id = resource['id']

            if service_type not in cost_details:
                cost_details[service_type] = {
                    'total_cost': 0,
                    'breakdown': collections.defaultdict(list)
                }

            if service_name not in price_mapping:
                price_spec = self._get_service_price(
                    service_name, service_type, products
                )
                price_mapping[service_name] = price_spec

            price_spec = price_mapping[service_name]

            # Convert volume according to unit in price definition.
            volume = float(
                general.convert_to(volume, unit, price_spec['unit'])
            )
            cost = (round(volume * price_spec['rate'], constants.PRICE_DIGITS)
                    if price_spec['rate'] else 0)

            total_cost += cost

            if detailed:
                cost_details[service_type]['total_cost'] = round(
                    (cost_details[service_type]['total_cost'] + cost),
                    constants.PRICE_DIGITS
                )
                cost_details[service_type]['breakdown'][
                    price_spec['product_name']
                ].append(
                    {
                        "resource_name": resource.get('name', ''),
                        "resource_id": res_id,
                        "cost": cost,
                        "quantity": round(volume, 3),
                        "rate": round(price_spec['rate'],
                                      constants.RATE_DIGITS),
                        "unit": price_spec['unit'],
                    }
                )

        result = {
            'total_cost': round(float(total_cost), constants.PRICE_DIGITS)
        }

        if detailed:
            result.update({'details': cost_details})

        return result

    def _normalize_credit(self, credit):
        return {
            "code": str(credit.voucher_code),
            "type": credit.credit_type[1],
            "start_date": credit.create_date,
            "expiry_date": credit.expiry_date,
            "balance": credit.current_balance,
            "recurring": False,
        }

    def get_credits(self, project_id, expiry_date):
        return [
            self._normalize_credit(c)
            for c in self.odoo_client.credit.list(
                [
                    ("project.os_id", "=", project_id),
                    ("expiry_date", ">", expiry_date.isoformat()),
                ],
                fields=[
                    "voucher_code",
                    "credit_type",
                    "create_date",
                    "expiry_date",
                    "current_balance",
                ],
            )
            if c.current_balance > 0.0001
        ]
