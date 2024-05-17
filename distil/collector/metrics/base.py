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


class BaseCollectorMetrics(object):
    """
    Distil Collector metrics processor base class.
    """

    @classmethod
    def load(cls):
        """
        Create the Distil Collector metrics processor.
        If it should not be created (e.g. disabled in config), return None.
        """
        raise NotImplementedError()

    def start(self):
        """
        Start the metrics processor service.
        """
        pass

    def stop(self):
        """
        Stop the metrics processor service.
        """
        pass

    def last_run_start(self, timestamp):
        """
        Update the Unix timestamp for the latest run's start time.
        """
        raise NotImplementedError()

    def last_run_end(self, timestamp):
        """
        Update the Unix timestamp for the latest run's end time.
        """
        raise NotImplementedError()

    def last_run_duration_seconds(self, duration):
        """
        Update the last collection run's duration, in seconds.
        """
        raise NotImplementedError()

    def usage(
        self,
        project_id,
        service,
        unit,
        resource_id,
        start,
        end,
        volume,
    ):
        """
        Update relevant metrics with the new usage entry.
        """
        raise NotImplementedError()
