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
import mock
from pbr.version import VersionInfo
from pkg_resources import get_distribution
from prometheus_client import (
    parser as prometheus_parser,
    make_wsgi_app as make_prometheus_wsgi_app,
)
from sqlalchemy import __version__ as sqlalchemy_version
from werkzeug.test import Client as WerkzeugClient
from werkzeug.wrappers import BaseResponse as WerkzeugResponse

from distil.collector.metrics.prometheus import PrometheusCollectorMetrics
from distil.collector import base as base_collector
from distil.db.sqlalchemy import api as db_api
from distil.tests.unit import base
from distil.version import version_info as distil_version_info


class PrometheusCollectorMetricsTest(base.DistilWithDbTestCase):

    def setUp(self):
        super(PrometheusCollectorMetricsTest, self).setUp()
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
        """Test the 'build_info' metric."""
        metrics_processor = PrometheusCollectorMetrics("127.0.0.1", 16799)
        for metric in prometheus_parser.text_string_to_metric_families(
            self.get_exporter_client(metrics_processor).get("/metrics").get_data(as_text=True),
        ):
            if metric.name == "distil_collector_build_info":
                self.assertEqual(metric.type, "gauge")
                self.assertEqual(
                    len(metric.samples),
                    1,
                    (
                        "Metric 'distil_collector_build_info' has incorrect "
                        "number of samples (got (%i, expected 1): %s"
                    ) % (len(metric.samples), str(metric.samples)),
                )
                sample = metric.samples[0]
                self.assertEqual(sample.name, "distil_collector_build_info")
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
            self.fail("Metric 'distil_collector_build_info' not found")

    def test_last_run_before(self):
        """Test the 'last_run' metrics before a collection run."""
        self._last_run_test(PrometheusCollectorMetrics("127.0.0.1", 16799))

    @mock.patch("distil.collector.base.BaseCollector.get_meter")
    def test_last_run_after(self, mock_get_meter):
        """Test the 'last_run' metrics after a collection run."""
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
        # Create a Distil collector object and
        # bind the Prometheus metrics processor to it.
        metrics_processor = PrometheusCollectorMetrics("127.0.0.1", 16799)
        collector = base_collector.BaseCollector(
            metrics_processors=[metrics_processor],
        )
        # Add a project and run a collection against it to provide metrics.
        db_api.project_add(
            {
                "id": project_id,
                "name": project_name,
                "description": project_description,
            }
        )
        collector.collect_usage(project, [(start_time, end_time)])
        # Run validity tests on the last_run metric samples.
        self._last_run_test(metrics_processor)

    def _last_run_test(self, metrics_processor):
        """Test the validity of the 'last_run' series of metrics."""
        client = self.get_exporter_client(metrics_processor)
        metrics = {
            metric.name: metric
            for metric in prometheus_parser.text_string_to_metric_families(
                client.get("/metrics").get_data(as_text=True),
            )
            if metric.name.startswith("distil_collector_last_run")
        }
        for metric in metrics.itervalues():
            self.assertEqual(metric.type, "gauge")
            self.assertEqual(
                len(metric.samples),
                1,
                (
                    "Metric '%s' has incorrect "
                    "number of samples (got (%i, expected 1): %s"
                ) % (metric.name, len(metric.samples), str(metric.samples)),
            )
            sample = metric.samples[0]
            self.assertEqual(sample.name, metric.name)
            self.assertEqual(sample.labels, {})
        last_run_start = (
            metrics["distil_collector_last_run_start"].samples[0].value
        )
        last_run_end = (
            metrics["distil_collector_last_run_end"].samples[0].value
        )
        last_run_duration_seconds = (
            metrics["distil_collector_last_run_duration_seconds"].samples[0].value
        )
        self.assertTrue(last_run_start < last_run_end)
        self.assertEqual(last_run_end - last_run_start, last_run_duration_seconds)

    @mock.patch("distil.collector.base.BaseCollector.get_meter")
    def test_usage_total(self, mock_get_meter):
        """Test the 'usage_total' metric."""
        project_id = "fake_project_id"
        project_name = "fake_project"
        project_description = "project for test"
        project = {"id": project_id, "name": project_name}
        container_name = "my_container"
        resource_id = "%s/%s" % (project_id, container_name)
        service = "o1.standard"
        unit = "byte"
        volume = 1024
        mock_get_meter.return_value = [
            {
                "resource_id": resource_id,
                "source": "openstack",
                "volume": volume,
            },
        ]
        start_time = datetime(year=2017, month=2, day=27)
        end_time = datetime(year=2017, month=2, day=27, hour=1)
        # Add a project to the database.
        db_api.project_add(
            {
                "id": project_id,
                "name": project_name,
                "description": project_description,
            }
        )
        # Create a Distil collector object and
        # bind the Prometheus metrics processor to it.
        metrics_processor = PrometheusCollectorMetrics("127.0.0.1", 16799)
        collector = base_collector.BaseCollector(
            metrics_processors=[metrics_processor],
        )
        client = self.get_exporter_client(metrics_processor)
        # Test that distil_collector_usage_total does not have any samples
        # when collections haven't run yet.
        for metric in prometheus_parser.text_string_to_metric_families(
            client.get("/metrics").get_data(as_text=True),
        ):
            if metric.name == "distil_collector_usage":
                if metric.samples:
                    self.fail(
                        (
                            "Metric 'distil_collector_usage_total' "
                            "has samples when it shouldn't:\n%s"
                        ) % "\n".join(
                            ("- %s" % str(sample))
                            for sample in metric.samples
                        ),
                    )
                else:
                    break
        else:
            self.fail("Metric 'distil_collector_usage_total' not found")
        # Run a collection against the added project to provide metrics.
        collector.collect_usage(project, [(start_time, end_time)])
        # Run validity tests on the usage_total metric samples.
        for metric in prometheus_parser.text_string_to_metric_families(
            client.get("/metrics").get_data(as_text=True),
        ):
            if metric.name == "distil_collector_usage":
                self.assertEqual(metric.type, "counter")
                self.assertEqual(
                    len(metric.samples),
                    1,
                    (
                        "Metric 'distil_collector_usage_total' has incorrect "
                        "number of samples (got (%i, expected 1): %s"
                    ) % (len(metric.samples), str(metric.samples)),
                )
                sample = metric.samples[0]
                self.assertEqual(sample.name, "distil_collector_usage_total")
                self.assertEqual(
                    sample.labels,
                    {
                        "project_id": project_id,
                        "service": service,
                        "unit": unit,
                    },
                )
                self.assertEqual(sample.value, volume)
                break
        else:
            self.fail("Metric 'distil_collector_usage_total' not found")

    def get_exporter_client(self, metrics_processor):
        """Create a client for sending requests to the Prometheus exporter."""
        return WerkzeugClient(
            make_prometheus_wsgi_app(registry=metrics_processor.registry),
            response_wrapper=WerkzeugResponse,
        )
