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

import uuid


class FakeCeilometerSample(object):
    def __init__(self, project_id, resource_id, meter, volume, timestamp, id=None, metadata=None):
        self.id = id or str(uuid.uuid4())
        self.project_id = project_id
        self.resource_id = resource_id
        self.meter = meter
        self.volume = float(volume)
        self.timestamp = timestamp
        self.metadata = metadata or {}

    def to_dict(self):
        return vars(self)

    def __repr__(self):
        return "FakeCeilometerSample({})".format(
            ", ".join("{}={}".format(k, repr(v)) for k, v in vars(self).iteritems()),
        )
