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

from keystoneauth1 import loading as ka_loading
from oslo_cache import core as cache
from oslo_config import cfg
from oslo_log import log
from oslo_utils import uuidutils

from distil import version

CONF = cfg.CONF

DEFAULT_OPTIONS = (
    cfg.IntOpt('port',
               default=9999,
               help='The port for the Distil API server',
               ),
    cfg.StrOpt('host',
               default='0.0.0.0',
               help='The listen IP for the Distil API server',
               ),
    cfg.ListOpt('public_api_routes',
                default=['/', '/v2/products', '/v2/collect'],
                help='The list of public API routes',
                ),
    cfg.StrOpt('erp_driver',
               default='odoo',
               help='The ERP driver used for Distil',
               ),
    cfg.StrOpt('exporter_host',
               default='0.0.0.0',
               help='The listen IP for the Distil Prometheus exporter',
               ),
    cfg.IntOpt('exporter_port',
               default=16798,
               help='The bind port for the Distil Prometheus exporter',
               ),
)

COLLECTOR_OPTS = [
    cfg.IntOpt('periodic_interval', default=3600,
               help=('Interval of usage collection.')),
    cfg.IntOpt('collect_window', default=1,
               help=('Window of usage collection in hours.')),
    cfg.StrOpt('collector_backend', default='ceilometer',
               help=('Data collector.')),
    cfg.IntOpt('max_windows_per_cycle', default=1,
               help=('The maximum number of windows per collecting cycle.')),
    cfg.IntOpt('max_collection_start_age',
               default=864,
               help=('The maximum time period for determining the start time '
                     'for usage collection on a new project, in hours. '
                     'Default is 864 hours (36 days). '
                     'Collection will start from the newest of: the project '
                     'creation timestamp (if available), the oldest '
                     "collected project's last collected time, or this value "
                     '(the fallback).')),
    cfg.StrOpt('meter_mappings_file', default='/etc/distil/meter_mappings.yml',
               help=('The meter mappings configuration.')),
    cfg.StrOpt('transformer_file', default='/etc/distil/transformer.yml',
               help=('The transformer configuration.')),
    cfg.ListOpt('include_domains', default=[],
                help=('Only collect usages for included domains.')),
    cfg.ListOpt('include_tenants', default=[],
                help=('Only collect usages for included tenants.')),
    cfg.ListOpt('ignore_tenants', default=[],
                help=('Do not collect usages for ignored tenants.')),
    cfg.ListOpt('trust_sources', default=[],
                help=('The list of resources that handled by collector.')),
    cfg.StrOpt('dawn_of_time', default='2014-04-01 00:00:00',
               deprecated_for_removal=True,
               deprecated_since='2024.1',
               deprecated_reason="Replaced by 'max_collection_start_age'.",
               help=('Unused.')),
    cfg.StrOpt('partitioning_suffix',
               help=('Collector partitioning group suffix. It is used when '
                     'running multiple collectors in favor of lock.')),
    cfg.StrOpt('project_order', default='ascending',
               choices=['ascending', 'descending', 'random'],
               help=('The order of project IDs to do usage collection. '
                     'Default is ascending.')),
    cfg.BoolOpt('enable_exporter', default=False,
                help=('Flag for enabling the Distil Collector '
                      'Prometheus exporter.')),
    cfg.StrOpt('exporter_host', default='0.0.0.0',
               help=('The listen IP for the Distil Collector '
                     'Prometheus exporter.')),
    cfg.IntOpt('exporter_port', default=16799,
               help=('The bind port for the Distil Collector '
                     'Prometheus exporter.')),
]

ODOO_OPTS = [
    cfg.StrOpt('version',
               default=None,
               required=False,
               help='Version of Odoo server.'),
    cfg.StrOpt('hostname',
               help='Host name of Odoo server.'),
    cfg.IntOpt('port', default=443,
               help='Port of Odoo server'),
    cfg.StrOpt('protocol', default='jsonrpc+ssl',
               help='Protocol to connect to Odoo server.'),
    cfg.StrOpt('database',
               help='Name of the Odoo database.'),
    cfg.StrOpt('user',
               help='Name of Odoo account to login.'),
    cfg.StrOpt('password', secret=True,
               help='Password of Odoo account to login.'),
    cfg.StrOpt('region_mapping',
               help='Region name mappings between Keystone and Odoo. For '
                    'example, '
                    'region_mapping=region1:RegionOne,region2:RegionTwo'),
    cfg.ListOpt('extra_product_category_list',
                default=[],
                help='Additional product categories which should be easily '
                     'parsed. Such as new product category created in Odoo.'),
    cfg.ListOpt('invisible_products', default=['reseller-margin-discount'],
                help=("The product list which will be invisible to project "
                      "users. For example, as a cloud provider we would like "
                      "to hide the reseller margin for reseller's customer.")),
    cfg.ListOpt('licensed_os_distro_list',
                default=[],
                help='A list of os_distro values for compute instances '
                     'to treat as "licensed" for billing purposes. '
                     'Instances running these distros will be charged an '
                     'additional licensing fee. In Odoo, the products should '
                     'be named "<flavor>-<os_distro>", e.g. c1.c1r2-windows '
                     'or c1.c2r4-sql-server-standard-windows.'),
    cfg.ListOpt('ignore_products_in_quotations',
                default=[],
                help='A list of products (services) to remove from '
                     'quotations. This is useful for hiding products for '
                     'services that are being collected by Distil, but are '
                     'not actually charged yet.'),
]

JSONFILE_OPTS = [
    cfg.StrOpt('products_file_path',
               default='/etc/distil/products.json',
               help='Json file to contain the products and prices.'),
    cfg.FloatOpt('tax_rate', default=0,
                 help='Tax rate for invoicing.'),
    cfg.ListOpt('ignore_products_in_quotations',
                default=[],
                help='A list of products (services) to remove from '
                     'quotations. This is useful for hiding products for '
                     'services that are being collected by Distil, but are '
                     'not actually charged yet.'),
]


CLI_OPTS = [
    cfg.StrOpt(
        'collect-end-time',
        help=('The end date of usage to collect before distil-collector is '
              'stopped. If not provided, distil-collector will keep running. '
              'Time format is %Y-%m-%dT%H:%M:%S')
    ),
]

AUTH_GROUP = 'keystone_authtoken'
ODOO_GROUP = 'odoo'
COLLECTOR_GROUP = 'collector'
JSONFILE_GROUP = 'jsonfile'


CONF.register_opts(DEFAULT_OPTIONS)
CONF.register_opts(ODOO_OPTS, group=ODOO_GROUP)
CONF.register_opts(JSONFILE_OPTS, group=JSONFILE_GROUP)
CONF.register_opts(COLLECTOR_OPTS, group=COLLECTOR_GROUP)
CONF.register_cli_opts(CLI_OPTS)


def list_opts():
    return [
        (ODOO_GROUP, ODOO_OPTS),
        (COLLECTOR_GROUP, COLLECTOR_OPTS),
        (None, DEFAULT_OPTIONS)
    ]


def _register_keystoneauth_opts(conf):
    # Register keystone authentication related options.
    from keystonemiddleware import auth_token  # noqa

    ka_loading.register_auth_conf_options(conf, AUTH_GROUP)


_register_keystoneauth_opts(CONF)

# This is simply a namespace for global config storage
main = None
rates_config = None
memcache = None
auth = None
collection = None
transformers = None


def setup_config(conf):
    global main
    main = conf['main']
    global rates_config
    rates_config = conf['rates_config']

    # special case to avoid issues with older configs
    try:
        global memcache
        memcache = conf['memcache']
    except KeyError:
        memcache = {'enabled': False}

    global auth
    auth = conf['auth']
    global collection
    collection = conf['collection']
    global transformers
    transformers = conf['transformers']


def parse_args(args=None, prog=None):
    log.set_defaults()
    log.register_options(CONF)
    CONF(
        args=args,
        project='distil',
        prog=prog,
        version=version.version_info.version_string(),
    )

    ka_loading.load_auth_from_conf_options(CONF, AUTH_GROUP)

    log.setup(CONF, prog)
