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

import abc
import hashlib
import re

from datetime import timedelta

import jmespath
import six
import yaml

from oslo_config import cfg
from oslo_log import log as logging

from distil.db import api as db_api
from distil import exceptions as exc
from distil import transformer as d_transformer
from distil.common import constants
from distil.common import openstack

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class BaseCollector(object):
    def __init__(self, metrics_processors=[]):
        # Meter-to-service mapping, stored as a YAML file.
        meter_file = CONF.collector.meter_mappings_file
        with open(meter_file, 'r') as f:
            try:
                self.meter_mappings = yaml.safe_load(f)
            except yaml.YAMLError:
                raise exc.InvalidConfig("Invalid yaml file: %s" % meter_file)
        # Metrics processors, managed by the collector service.
        # Used to publish project-specific metrics.
        self.metrics_processors = metrics_processors

    @abc.abstractmethod
    def get_meter(self, project, meter, start, end):
        raise NotImplementedError

    def collect_usage(self, project, windows):
        """Collect usage for specific tenant.

        :return: True if no error happened otherwise return False.
        """
        LOG.info('collect_usage by %s for project: %s(%s)' %
                 (self.__class__.__name__, project['id'], project['name']))

        for window_start, window_end in windows:
            LOG.info("Project %s(%s) slice %s %s", project['id'],
                     project['name'], window_start, window_end)

            resources = {}
            usage_entries = []

            try:
                for mapping in self.meter_mappings:
                    # Invoke get_meter function of specific collector.
                    usage = self.get_meter(project['id'], mapping['meter'],
                                           window_start, window_end)

                    usage_by_resource = {}
                    self._filter_and_group(usage, usage_by_resource)
                    self._transform_usages(project['id'], usage_by_resource,
                                           mapping, window_start, window_end,
                                           resources, usage_entries)

                # Insert resources and usage_entries, and update last collected
                # time of project within one session.
                db_api.usages_add(project['id'], resources, usage_entries,
                                  window_end)

                LOG.info('Finish project %s(%s) slice %s %s', project['id'],
                         project['name'], window_start, window_end)
            except Exception as e:
                LOG.exception(
                    "Collection failed for %s(%s) in window: %s - %s, reason: "
                    "%s", project['id'], project['name'],
                    window_start.strftime(constants.iso_time),
                    window_end.strftime(constants.iso_time),
                    str(e)
                )
                return False

        return True

    def _filter_and_group(self, usage, usage_by_resource):
        trust_sources = set(CONF.collector.trust_sources)
        for u in usage:
            # if we have a list of trust sources configured, then
            # discard everything not matching.
            # NOTE(flwang): When posting samples by ceilometer REST API, it
            # will use the format <tenant_id>:<source_name_from_user>
            # so we need to use a regex to recognize it.
            if (trust_sources and
                    all([not re.match(source, u['source'])
                         for source in trust_sources])):
                LOG.warning('Ignoring untrusted usage sample from source `%s`',
                            u['source'])
                continue

            resource_id = u['resource_id']
            entries = usage_by_resource.setdefault(resource_id, [])
            entries.append(u)

    def _get_os_distro(self, entry):
        """Gets os distro info for instance.

        1. If instance is booted from image, get distro info from image_ref_url
           in sample's metadata.
        2. If instance is booted from volume, get distro info from
           volume_image_metadata property of the root volume.
        3. If instance is booted from volume and it's already been deleted,
           use default value('unknown').
        """
        os_distro = 'unknown'
        root_vol = None

        try:
            # Check if the VM is booted from volume first. When VM is booted
            # from a windows image and do a rebuild using a linux image, the
            # 'image_ref' property will be set inappropriately.
            root_vol = openstack.get_root_volume(entry['resource_id'])
        except Exception as e:
            LOG.warning(
                'Error occurred when getting root_volume for %s, reason: %s' %
                (entry['resource_id'], str(e))
            )

        if root_vol:
            image_meta = getattr(root_vol, 'volume_image_metadata', {})
            os_distro = image_meta.get('os_distro', 'unknown')
        else:
            # 'image_ref_url' is always there no matter it is sample created by
            # Ceilometer pollster or sent by notification. For instance booted
            # from volume the value is string 'None' in Ceilometer client
            # response.
            image_url = entry['metadata']['image_ref_url']

            if image_url and image_url != 'None':
                image_id = image_url.split('/')[-1]

                try:
                    os_distro = getattr(
                        openstack.get_image(image_id),
                        'os_distro',
                        'unknown'
                    )
                except Exception as e:
                    LOG.warning(
                        'Error occurred when getting image %s, reason: %s' %
                        (image_id, str(e))
                    )

        return os_distro

    def _get_resource_info(self, project_id, resource_id, resource_type, entry,
                           defined_meta):
        resource_info = {'type': resource_type}

        for field, parameters in defined_meta.items():
            for source in parameters['sources']:
                try:
                    value = entry['metadata'][source]
                    resource_info[field] = (
                        parameters['template'] % value
                        if 'template' in parameters else value
                    )
                    break
                except KeyError:
                    # Just means we haven't found the right value yet.
                    # Or value isn't present.
                    pass

        # If the resource is already created, don't update properties below.
        if not db_api.resource_get_by_ids(project_id, [resource_id]):
            if resource_type == 'Virtual Machine':
                resource_info['os_distro'] = self._get_os_distro(entry)
            if resource_type == 'Object Storage Container':
                # NOTE(flwang): It's safe to get container name by /, since
                # Swift doesn't allow container name with /.
                # NOTE(flwang): Instead of using the resource_id from the
                # input parameters, here we use the original resource id from
                # the entry. Because the resource_id has been hashed(MD5) to
                # avoid too long.
                idx = entry['resource_id'].index('/') + 1
                resource_info['name'] = entry['resource_id'][idx:]

        return resource_info

    def _transform_usages(self, project_id, usage_by_resource, mapping,
                          window_start, window_end, resources, usage_entries):
        service = (mapping['service'] if 'service' in mapping
                   else mapping['meter'])

        transformer = d_transformer.get_transformer(
            mapping['transformer'],
            override_config=mapping.get('transformer_config', {}))

        for res_id, entries in usage_by_resource.items():
            res_id = mapping.get('res_id_template', '%s') % res_id

            # NOTE(callumdickinson): If one or more meter mapping filters are
            # defined, use them to drop samples that should not be considered
            # when creating usage entries.
            if "filters" in mapping and mapping["filters"]:
                entries = (
                    sample
                    for sample in entries
                    if self._sample_filter(mapping["filters"], sample)
                )

            # NOTE(callumdickinson): Handle any volume handling options.
            if "volume" in mapping and mapping["volume"]:
                volume_config = mapping["volume"]
                if isinstance(volume_config, dict):
                    # NOTE(callumdickinson): If the meter mapping specifies
                    # a custom volume source, overwrite the volume in the
                    # samples with the values located using the defined
                    # search expression (or list of expressions).
                    # If a list of expressions, use the first match.
                    for key in ("sources", "source"):
                        if key in volume_config and volume_config[key]:
                            volume_sources = volume_config[key]
                            entries = (
                                dict(
                                    sample,
                                    volume=self._sample_search(
                                        field="volume",
                                        expression=volume_sources,
                                        sample=sample,
                                        value_type=float,
                                    ),
                                )
                                for sample in entries
                            )
                # NOTE(callumdickinson): If volume is defined and is a
                # non-None value, but does not fall into any other category,
                # assume it is an override to set the volume to a fixed value
                # and set that on all samples.
                else:
                    entries = (
                        dict(sample, volume=float(volume_config))
                        for sample in entries
                    )

            # NOTE(callumdickinson): Render any sample filters applied above.
            entries = list(entries)
            LOG.debug(
                (
                    "Post-preprocessing, pre-transformation usage "
                    "for resource %s: %s"
                ),
                res_id,
                entries,
            )
            if not entries:
                LOG.debug(
                    (
                        "Pre-processing filtered out all usage for "
                        "resource %s, skipping"
                    ),
                    res_id,
                )
                continue

            transformed = transformer.transform_usage(
                service, entries, window_start, window_end
            )

            if transformed:
                # NOTE(flwang): Currently the column size of resource id in DB
                # is 100 chars, but the container name of swift could be 256,
                # plus project id and a '/', the id for a swift container
                # could be 32+1+256. So this is a fix for the problem. But
                # instead of checking the length of resource id, here I'm
                # hashing the name only for swift to get a consistent
                # id for swift billing. Another change will be proposed to
                # openstack-billing to handle this case as well.
                if mapping['type'] == "Object Storage Container":
                    res_id = hashlib.md5(res_id.encode('utf-8')).hexdigest()

                LOG.debug(
                    'After transformation, usage for resource %s: %s' %
                    (res_id, transformed)
                )

                res_info = self._get_resource_info(
                    project_id,
                    res_id,
                    mapping['type'],
                    entries[-1],
                    mapping['metadata']
                )

                res = resources.setdefault(res_id, res_info)
                res.update(res_info)

                for service, volume in transformed.items():
                    entry = {
                        'service': service,
                        'volume': volume,
                        'unit': mapping['unit'],
                        'resource_id': res_id,
                        'start': window_start,
                        'end': window_end,
                        'tenant_id': project_id
                    }
                    usage_entries.append(entry)
                    # Push the usage entry to all active metrics processors.
                    for metrics_processor in self.metrics_processors:
                        metrics_processor.usage(
                            project_id=entry["tenant_id"],
                            service=entry["service"],
                            unit=entry["unit"],
                            resource_id=entry["resource_id"],
                            start=entry["start"],
                            end=entry["end"],
                            volume=entry["volume"],
                        )

    @classmethod
    def _sample_search(
        cls,
        field,
        expression,
        sample,
        optional=False,
        default=0,
        value_type=None,
    ):
        if isinstance(expression, six.string_types):
            expressions = [expression]
            expressions_str = "search expression '{}'".format(expression)
        else:  # list
            expressions = expression
            expressions_str = "search expressions {}".format(expression)
        for search_expr in expressions:
            value = jmespath.search(search_expr, sample)
            if value is not None:
                if value_type:
                    try:
                        return value_type(value)
                    except ValueError as err:
                        raise exc.SearchExpressionValueTypeError(
                            (
                                "Unable to convert value found for "
                                "field '{}' using {} in sample to type '{}': "
                                "{} (search expression: {}, value: {}, "
                                "sample: {})"
                            ).format(
                                field,
                                expressions_str,
                                value_type.__name__,
                                err,
                                repr(search_expr),
                                repr(value),
                                repr(sample),
                            ),
                        )
                return value
        if optional:
            LOG.warning(
                (
                    "Value not found for field '{}' using {} in sample: {}"
                    " -> using the default value of {}"
                ).format(
                    field,
                    expressions_str,
                    sample,
                    default,
                ),
            )
            return default
        raise exc.SearchExpressionNotFoundError(
            "Value not found for field '{}' using {} in sample: {}".format(
                field,
                expressions_str,
                sample,
            ),
        )

    @classmethod
    def _sample_filter(cls, filters, sample):
        # NOTE(callumdickinson): Only allow the sample if *ALL* filters
        # return a positive result.
        for filter in filters:
            result = jmespath.search(filter, sample)
            if not result:
                LOG.debug(
                    (
                        "Dropping sample due to meter mapping filter result: "
                        "sample=%s, filters=%s, filter=%s, result=%s"
                    ),
                    sample,
                    filters,
                    filter,
                    result,
                )
                return False
        LOG.debug(
            (
                "Sample passed through meter mapping filters: "
                "sample=%s, filters=%s"
            ),
            sample,
            filters,
        )
        return True
