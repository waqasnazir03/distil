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

import flask

from distil.api import v2 as api_v2
from distil.common import api
from distil.tests.unit import base


class APITest(base.DistilWithDbTestCase):
    def setUp(self):
        super(APITest, self).setUp()

        self.app = flask.Flask(__name__)

        @self.app.route('/', methods=['GET'])
        def version_list():
            return api.render({
                "versions": [
                    {"id": "v2", "status": "CURRENT"}
                ]})

        self.app.register_blueprint(api_v2.rest, url_prefix="/v2")
        self.client = self.app.test_client()
