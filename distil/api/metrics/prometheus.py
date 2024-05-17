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

from datetime import datetime
from platform import python_version

import eventlet
from flask import __version__ as flask_version
from oslo_config import cfg
from pbr.version import VersionInfo
from pkg_resources import get_distribution
from prometheus_client import CollectorRegistry
from prometheus_client import Info
from prometheus_client import make_wsgi_app as make_exporter_wsgi_app
from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import __version__ as sqlalchemy_version

from distil import config
from distil.db import api as db_api
from distil.version import version_info as distil_version_info

CONF = cfg.CONF


class DistilPrometheusCollector(object):
    """
    Prometheus collector for Distil metrics.
    """

    def collect(self):
        """
        Collect Distil metrics, and yield them to the
        Prometheus exporter request processor.
        """
        # Expose the `last_collected` value for each project
        # as a Prometheus metric.
        # This value represents the point of time up to which billing
        # for the project has been collected.
        last_collected_metric = GaugeMetricFamily(
            name="distil_last_collected",
            documentation=(
                "Unix timestamp for age of collection for each project"
            ),
            labels=("project_id",),
        )
        for project_id, last_collected in db_api.get_last_collected_all():
            last_collected_metric.add_metric(
                labels=(project_id,),
                value=(
                    last_collected - datetime(1970, 1, 1)
                ).total_seconds(),
            )
        yield last_collected_metric


def make_wsgi_app():
    """
    Create and return the Prometeus exporter WSGI app
    based on the currently loaded configuration.
    """

    # Create the Prometheus collector registry.
    registry = CollectorRegistry()

    # Add a Distil build information metric.
    # This exposes the version numbers of various packages and runtimes.
    # The metric can also be used to determine if the exporter is active.
    build_info = Info(
        name="distil_build",
        documentation="Distil build information",
        registry=registry,
    )
    build_info.info(
        {
            "version": distil_version_info.version_string(),
            "ceilometer_client_version": VersionInfo(
                "python-ceilometerclient",
            ).version_string(),
            "cinder_client_version": VersionInfo(
                "python-cinderclient",
            ).version_string(),
            "glance_client_version": VersionInfo(
                "python-glanceclient",
            ).version_string(),
            "keystone_client_version": VersionInfo(
                "python-keystoneclient",
            ).version_string(),
            "keystone_middleware_version": VersionInfo(
                "keystonemiddleware",
            ).version_string(),
            "keystone_auth1_version": VersionInfo(
                "keystoneauth1",
            ).version_string(),
            "neutron_client_version": VersionInfo(
                "python-neutronclient",
            ).version_string(),
            "nova_client_version": VersionInfo(
                "python-novaclient",
            ).version_string(),
            "oslo_cache_version": VersionInfo(
                "oslo.cache",
            ).version_string(),
            "oslo_config_version": VersionInfo(
                "oslo.config",
            ).version_string(),
            "oslo_context_version": VersionInfo(
                "oslo.context",
            ).version_string(),
            "oslo_db_version": VersionInfo(
                "oslo.db",
            ).version_string(),
            "oslo_i18n_version": VersionInfo(
                "oslo.i18n",
            ).version_string(),
            "oslo_log_version": VersionInfo(
                "oslo.log",
            ).version_string(),
            "oslo_policy_version": VersionInfo(
                "oslo.policy",
            ).version_string(),
            "oslo_serialization_version": VersionInfo(
                "oslo.serialization",
            ).version_string(),
            "oslo_service_version": VersionInfo(
                "oslo.service",
            ).version_string(),
            "oslo_utils_version": VersionInfo(
                "oslo.utils",
            ).version_string(),
            "sqlalchemy_version": sqlalchemy_version,
            "flask_version": flask_version,
            "eventlet_version": eventlet.__version__,
            "prometheus_client_version": get_distribution(
                "prometheus-client",
            ).version,
            "python_version": python_version(),
        },
    )

    # Register the dynamic metric collector object to the registry.
    registry.register(DistilPrometheusCollector())

    # Create the Prometheus exporter WSGI app and map it
    # to the custom registry.
    return make_exporter_wsgi_app(registry=registry)


def make_app(args=None):
    """
    Load the configuration, and return a WSGI app for Distil Exporter.
    """

    config.parse_args(args, "distil-exporter")
    return make_wsgi_app()
