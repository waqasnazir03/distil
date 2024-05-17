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

import datetime

from oslo_log import log as logging

from distil.transformer import BaseTransformer
from distil.common import constants
from distil.common import openstack

LOG = logging.getLogger(__name__)


class NumboolTransformer(BaseTransformer):
    """Transformer for whether a resource existed at all in the
    given time period.

    If the resource volume is any value higher than 0 is found, then
    the number of hours within the period is returned as the
    rated volume. If the resource volume is 0, the rated volume
    will also be 0.
    """

    def _transform_usage(self, meter_name, raw_data, start_at, end_at):
        for sample in raw_data:
            if sample["volume"] and sample["volume"] > 0:
                return {meter_name: 1}
        return {meter_name: 0}


class MaxTransformer(BaseTransformer):
    """Transformer for max-integration of a gauge value over time.
    If the raw unit is 'gigabytes', then the transformed unit is
    'gigabyte-hours'.
    """

    def _get_max_vol(self, data):
        if len(data):
            max_vol = max([(v["volume"] if v["volume"] else 0) for v in data])
            if max_vol:
                return max_vol
        return 0

    def _transform_usage(self, meter_name, raw_data, start_at, end_at):
        max_vol = self._get_max_vol(raw_data)

        hours = (end_at - start_at).total_seconds() / 3600.0

        return {meter_name: max_vol * hours}


class BlockStorageMaxTransformer(MaxTransformer):
    """
    Variantion on the GaugeMax Transformer that checks for
    volume_type and uses that as the service, or uses the
    default service name.
    """

    def _transform_usage(self, name, data, start, end):
        if not data:
            return None

        max_vol = self._get_max_vol(data)

        if "volume_type" in data[-1]['metadata']:
            vtype = data[-1]['metadata']['volume_type']
            service = openstack.get_volume_type_name(vtype)
            if not service:
                service = name
        else:
            service = name

        hours = (end - start).total_seconds() / 3600.0
        return {service: max_vol * hours}


class DatabaseVolumeMaxTransformer(BaseTransformer):
    """
    Variantion on the GaugeMax Transformer that checks for
    volume_type and uses that as the service, or uses the
    default service name.

    It also gets the actual volume size from metadata.
    """

    def _transform_usage(self, name, data, start, end):
        if not data:
            return None

        vols = []
        for v in data:
            volume_size = v["metadata"]["volume.size"]
            try:
                vol = int(volume_size)
            except ValueError:
                vol = int(float(volume_size))
            vols.append(vol)
        max_vol = max(vols)

        volume_type = openstack.get_volume_type_for_volume(
            data[-1]['metadata']['volume_id'])
        if not volume_type:
            return None

        hours = (end - start).total_seconds() / 3600.0
        return {volume_type: max_vol * hours}


class ObjectStorageMaxTransformer(MaxTransformer):
    """
    Variantion on the GaugeMax Transformer that checks for
    object storage container policy and uses that as the service,
    or uses the default service name.
    """

    def _transform_usage(self, name, data, start, end):
        if not data:
            return None

        container_name = data[-1]['resource_id'].split('/')[1]
        project_id = data[-1]['project_id']

        service = openstack.get_container_policy(project_id, container_name)
        if not service:
            service = name

        max_vol = self._get_max_vol(data)

        hours = (end - start).total_seconds() / 3600.0
        return {service: max_vol * hours}


class SumTransformer(BaseTransformer):
    """Transformer for sum-integration of a gauge value for given period.
    """

    def _transform_usage(self, meter_name, raw_data, start_at, end_at):
        sum_vol = 0
        for sample in raw_data:
            try:
                t = datetime.datetime.strptime(sample['timestamp'],
                                               '%Y-%m-%dT%H:%M:%S.%f')
            except ValueError:
                # In case of u'timestamp': u'2016-08-04T11:35:00',
                t = datetime.datetime.strptime(sample['timestamp'],
                                               '%Y-%m-%dT%H:%M:%S')

            if t >= start_at and t < end_at:
                sum_vol += sample["volume"] or 0

        return {meter_name: sum_vol}
