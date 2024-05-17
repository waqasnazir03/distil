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
import os
from platform import python_version

from eventlet import __version__ as eventlet_version
from flask import __version__ as flask_version
import mock
from pbr.version import VersionInfo
from pkg_resources import get_distribution
from prometheus_client import parser as prometheus_parser
from sqlalchemy import __version__ as sqlalchemy_version
from werkzeug.test import Client as WerkzeugClient
from werkzeug.wrappers import BaseResponse as WerkzeugResponse

from distil.api.metrics.prometheus import make_wsgi_app
from distil.collector import base as base_collector
from distil.db.sqlalchemy import api as db_api
from distil.tests.unit import base
from distil.version import version_info as distil_version_info


class PrometheusAPIMetricsTest(base.DistilWithDbTestCase):

    def setUp(self):
        super(PrometheusAPIMetricsTest, self).setUp()
        meter_mapping_file = os.path.join(
            os.environ["DISTIL_TESTS_CONFIGS_DIR"],
            "meter_mappings.yaml",
        )
        self.conf.set_default(
            "meter_mappings_file",
            meter_mapping_file,
            group="collector",
        )
        transformer_file = os.path.join(
            os.environ["DISTIL_TESTS_CONFIGS_DIR"],
            "transformer.yaml",
        )
        self.conf.set_default(
            "transformer_file",
            transformer_file,
            group="collector",
        )

    def test_build_info(self):
        """Test the 'distil_build_info' Prometheus metric."""
        for metric in prometheus_parser.text_string_to_metric_families(
            self.get_exporter_client().get("/metrics").get_data(as_text=True),
        ):
            if metric.name == "distil_build_info":
                self.assertEqual(metric.type, "gauge")
                self.assertEqual(
                    len(metric.samples),
                    1,
                    (
                        "Metric 'distil_build_info' has incorrect "
                        "number of samples (got (%i, expected 1): %s"
                    ) % (len(metric.samples), str(metric.samples)),
                )
                sample = metric.samples[0]
                self.assertEqual(sample.name, "distil_build_info")
                self.assertEqual(
                    sample.labels,
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
                        "eventlet_version": eventlet_version,
                        "prometheus_client_version": get_distribution(
                            "prometheus-client",
                        ).version,
                        "python_version": python_version(),
                    },
                )
                self.assertEqual(sample.value, 1.0)
                break
        else:
            self.fail("Metric 'distil_build_info' not found")

    @mock.patch("distil.collector.base.BaseCollector.get_meter")
    def test_last_collected(self, mock_get_meter):
        """Test the 'distil_last_collected' Prometheus metric."""
        project_id = "fake_project_id"
        project_name = "fake_project"
        project_description = "project for test"
        project = {"id": project_id, "name": project_name}
        container_name = "my_container"
        resource_id = "%s/%s" % (project_id, container_name)
        mock_get_meter.return_value = [
            {
                "resource_id": resource_id,
                "source": "openstack",
                "volume": 1024,
            },
        ]
        start_time = datetime(year=2017, month=2, day=27)
        end_time = datetime(year=2017, month=2, day=27, hour=1)
        collector = base_collector.BaseCollector()
        client = self.get_exporter_client()
        # Test that distil_last_collected does not have any samples
        # without any projects defined.
        for metric in prometheus_parser.text_string_to_metric_families(
            client.get("/metrics").get_data(as_text=True),
        ):
            if metric.name == "distil_last_collected":
                if metric.samples:
                    self.fail(
                        (
                            "Metric 'distil_last_collected' has samples "
                            "when it shouldn't:\n%s"
                        ) % "\n".join(
                            ("- %s" % str(sample))
                            for sample in metric.samples
                        ),
                    )
                else:
                    break
        else:
            self.fail("Metric 'distil_last_collected' not found")
        # Add a project and run a collection against it to provide metrics.
        db_api.project_add(
            {
                "id": project_id,
                "name": project_name,
                "description": project_description,
            }
        )
        collector.collect_usage(project, [(start_time, end_time)])
        # Check that the corresponding distil_last_collected metric
        # was created.
        for metric in prometheus_parser.text_string_to_metric_families(
            client.get("/metrics").get_data(as_text=True),
        ):
            if metric.name == "distil_last_collected":
                self.assertEqual(metric.type, "gauge")
                self.assertEqual(
                    len(metric.samples),
                    1,
                    (
                        "Metric 'distil_last_collected' has incorrect "
                        "number of samples (got (%i, expected 1): %s"
                    ) % (len(metric.samples), str(metric.samples)),
                )
                sample = metric.samples[0]
                self.assertEqual(sample.name, "distil_last_collected")
                self.assertEqual(sample.labels, {"project_id": project_id})
                self.assertEqual(
                    sample.value,
                    (end_time - datetime(1970, 1, 1)).total_seconds(),
                )
                break
        else:
            self.fail("Metric 'distil_last_collected' not found")

    def get_exporter_client(self):
        """Create a client for sending requests to the Prometheus exporter."""
        return WerkzeugClient(
            make_wsgi_app(),
            response_wrapper=WerkzeugResponse,
        )
