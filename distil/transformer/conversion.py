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

from __future__ import division

from datetime import datetime

from distil.transformer import BaseTransformer
from distil.common import constants
from distil.common import openstack


class UpTimeTransformer(BaseTransformer):
    """
    Transformer for discovering all flavours a compute instance
    was running as within the window.

    Previous versions of this transformer attempted to extrapolate
    the instance uptime from the telemetry samples,
    based on their collection timestamp.

    This was not accurate, as that merely corresponds to when the
    telemetry agent polled for the instance, not actual uptime.
    This never returned a "full" uptime value for a window, either,
    without hacking the start/end time to have the transformer look at
    the previous hour, as well.
    """

    @property
    def tracked_states(self):
        if not hasattr(self, "_tracked_states"):
            self._tracked_states = set(
                (state.upper() for state in self.config["tracked_states"]),
            )
        return self._tracked_states

    @property
    def service_prefix(self):
        return self.config.get("prefix") or ""

    def get_state(self, sample):
        return sample["metadata"].get(
            "status",
            sample["metadata"].get("state", ""),
        ).upper()

    def get_flavor(self, sample):
        return sample["metadata"].get("instance_type")

    def _transform_usage(self, name, data, start, end):
        # Discover what flavors the instance was running as within the window.
        sampled_flavors = set()
        for sample in data:
            if self.get_state(sample) not in self.tracked_states:
                continue
            flavor = self.get_flavor(sample)
            if flavor:
                sampled_flavors.add(flavor)
        # Divide the total time within the window equally between the sampled
        # flavor types the instance was running as within the window,
        # and return all of them.
        if not sampled_flavors:
            return {}
        volume = (end - start).total_seconds() / len(sampled_flavors)
        return {
            "{}{}".format(self.service_prefix, flavor): volume
            for flavor in sampled_flavors
        }


class FromImageTransformer(BaseTransformer):
    """
    Transformer for creating Volume entries from instance metadata.
    Checks if image was booted from image, and finds largest root
    disk size among entries.
    This relies heaviliy on instance metadata.
    """

    def _transform_usage(self, name, data, start, end):
        checks = self.config['md_keys']
        none_values = self.config['none_values']
        service = self.config['service']
        size_sources = self.config['size_keys']

        size = 0
        for entry in data:
            for source in checks:
                try:
                    if (entry['metadata'][source] in none_values):
                        return None
                    break
                except KeyError:
                    pass
            for source in size_sources:
                try:
                    root_size = float(entry['metadata'][source])
                    if root_size > size:
                        size = root_size
                except KeyError:
                    pass

        hours = (end - start).total_seconds() // 3600.0

        return {service: size * hours}


class NetworkServiceTransformer(BaseTransformer):
    """Transformer for Neutron network service, such as LBaaS, VPNaaS,
    FWaaS, etc.
    """

    def _transform_usage(self, name, data, start, end):
        # NOTE(flwang): The network service pollster of Ceilometer is using
        # status as the volume(see https://github.com/openstack/ceilometer/
        # blob/master/ceilometer/network/services/vpnaas.py#L55), so we have
        # to check the volume to make sure only the active service is
        # charged(0=inactive, 1=active).
        volumes = [v["volume"] for v in data if
                   v["volume"] < 2]
        max_vol = max(volumes) if len(volumes) else 0
        hours = (end - start).total_seconds() // 3600.0
        return {name: max_vol * hours}


class DatabaseManagementUpTimeTransformer(UpTimeTransformer):
    """
    Transformer for discovering all flavour a database instance
    was running as within the widndow.

    While this uses the base `uptime` transformer logic,
    the service name here needs to be a variant of the flavor
    prefixed with a database specific value, in this case `db.`,
    which will mean a flavor of `c1.c1r2` will become `db.c1.c1r2`
    for the service in the usage entry.
    """

    def get_state(self, sample):
        return sample["metadata"].get("status", "").upper()

    def get_flavor(self, sample):
        return openstack.get_flavor_name(sample["metadata"].get("flavor.id"))
