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
import json

from dateutil import parser
from oslo_log import log
from oslo_utils import strutils
from stevedore import driver

from distil import exceptions
from distil.api import acl
from distil.common import api
from distil.common import constants
from distil.common import openstack
from distil.service import collector
from distil.service.api.v2 import credits
from distil.service.api.v2 import health
from distil.service.api.v2 import invoices
from distil.service.api.v2 import measurements
from distil.service.api.v2 import products
from distil.service.api.v2 import quotations

from distil import transformer as d_transformer

LOG = log.getLogger(__name__)

rest = api.Rest('v2', __name__)


def _get_request_args():
    cur_project_id = api.context.current().project_id
    project_id = api.get_request_args().get('project_id', cur_project_id)

    if not api.context.current().is_admin and cur_project_id != project_id:
        raise exceptions.Forbidden()

    start = api.get_request_args().get('start', None)
    end = api.get_request_args().get('end', None)

    detailed = strutils.bool_from_string(
        api.get_request_args().get('detailed', False)
    )

    regions = api.get_request_args().get('regions', None)

    params = {
        'start': start,
        'end': end,
        'project_id': project_id,
        'detailed': detailed,
        'regions': regions
    }

    return params


@rest.post('/collect')
def collect_post(data):
    #LOG.error(flask.request.authorization)
    meters = json.dumps(data)
    # meters looks like following:
    """
	[
    {
      "project_name":null,
      "user_id":"0b937d43fbba4cffaf0a610f2efe629a",
      "name":"vcpus",
      "resource_id":"0810bedc-b9ba-44d5-8e89-f3c06d7d14b8",
      "user_name":null,
      "id":"ea68ad34-3f90-11ef-8776-fa163e81cf8e",
      "volume":1,
      "source":"openstack",
      "monotonic_time":null,
      "timestamp":"2024-07-11T14:21:51.224060+00:00",
      "project_id":"a0195af1c0fd470daa67f6da933ac38e",
      "type":"gauge",
      "resource_metadata":{
         "display_name":"waqas-2510",
         "created_at":"2024-06-19 14:35:19+00:00",
         "host":"toolbox-cloud-1.novalocal",
         "flavor_id":"e38b4d18-abcf-492e-b71c-1921fd7e8117",
         "launched_at":"2024-06-19T14:35:35.000000",
         "flavor_name":"test"
      },
      "unit":"vcpu"
    },
    {
      "project_name":null,
      "user_id":"0b937d43fbba4cffaf0a610f2efe629a",
      "name":"memory",
      "resource_id":"0810bedc-b9ba-44d5-8e89-f3c06d7d14b8",
      "user_name":null,
      "id":"ea68be78-3f90-11ef-8776-fa163e81cf8e",
      "volume":512,
      "source":"openstack",
      "monotonic_time":null,
      "timestamp":"2024-07-11T14:21:51.224060+00:00",
      "project_id":"a0195af1c0fd470daa67f6da933ac38e",
      "type":"gauge",
      "resource_metadata":{
         "display_name":"waqas-2510",
         "created_at":"2024-06-19 14:35:19+00:00",
         "host":"toolbox-cloud-1.novalocal",
         "flavor_id":"e38b4d18-abcf-492e-b71c-1921fd7e8117",
         "launched_at":"2024-06-19T14:35:35.000000",
         "flavor_name":"test"
      },
      "unit":"MB"
    }
    ]
    """
    #creds = api.get_request_creds()
    meter_mapping=[{'meter': 'instance', 'type': 'Virtual Machine', 'transformer': 'uptime', 'unit': 'second', 'metadata': {'name': {'sources': ['display_name']}, 'availability zone': {'sources': ['OS-EXT-AZ:availability_zone']}, 'host': {'sources': ['host']}}}]
    uptime_transformer = {'uptime': {'tracked_states': ['active', 'paused', 'rescue', 'rescued', 'resize', 'resized', 'verify_resize', 'suspended', 'shutoff', 'stopped']}}
    LOG.error(meters)
    resource_id=None
    if len(data) and data[0].get("resource_id"):
        resource_id = data[0].get("resource_id")
    else:
        return "Invalid data"
    usage_data = {resource_id: data}
    LOG.error(usage_data)
    vm_mapping=meter_mapping[0]

    service = (vm_mapping['service'] if 'service' in vm_mapping
                   else vm_mapping['meter'])
    LOG.error(service)
    transformer = d_transformer.get_transformer(
            vm_mapping['transformer'],
            override_config=vm_mapping.get('transformer_config', {}))

    #LOG.error(service)
    #LOG.error(transformer)
    """
    transformed = transformer.transform_usage(
                service, entries, window_start, window_end
            )
    """

    # Uptime transformer's _tranform_usage method requires state key in resource_metadata dict in resource sample.
    # https://github.com/waqasnazir03/distil/blob/master/distil/transformer/conversion.py#L66
    # In my env I am not seeing this key.
    # https://docs.openstack.org/ceilometer/zed/admin/telemetry-measurements.html says we can configure additional keys reserved_metadata_keys
    # in ceilometer.conf.DEFAULT. It isn't working atm.
    return api.render(collection=usage_data)

@rest.get('/health')
@acl.enforce("health:get")
def health_get():
    return api.render(health=health.get_health())


@rest.get('/products')
def products_get():
    params = _get_request_args()

    os_regions = params.get('regions')
    regions = os_regions.split(',') if os_regions else []

    if regions:
        actual_regions = [r.id for r in openstack.get_regions()]

        if not set(regions).issubset(set(actual_regions)):
            raise exceptions.NotFoundException(
                'Region name(s) %s not found, available regions: %s' %
                (list(set(regions) - set(actual_regions)),
                 actual_regions)
            )
    return api.render(products=products.get_products(regions))


@rest.get('/measurements')
@acl.enforce("rating:measurements:get")
def measurements_get():
    params = _get_request_args()

    return api.render(
        measurements=measurements.get_measurements(
            params['project_id'], params['start'], params['end']
        )
    )


@rest.get('/invoices')
@acl.enforce("rating:invoices:get")
def invoices_get():
    params = _get_request_args()

    return api.render(
        invoices.get_invoices(
            params['project_id'],
            params['start'],
            params['end'],
            detailed=params['detailed']
        )
    )


@rest.get('/quotations')
@acl.enforce("rating:quotations:get")
def quotations_get():
    params = _get_request_args()

    return api.render(
        quotations.get_quotations(
            params['project_id'], detailed=params['detailed']
        )
    )


@rest.get('/credits')
@acl.enforce("rating:credits:get")
def credits_get():
    params = _get_request_args()

    return api.render(credits=credits.get_credits(params['project_id']))
