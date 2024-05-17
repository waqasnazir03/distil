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

import logging
import sys

import eventlet
import eventlet.wsgi
from oslo_config import cfg
from oslo_log import log

from distil.api.metrics.prometheus import make_app

CONF = cfg.CONF
LOG = log.getLogger(__name__)


class WritableLogger(object):
    """
    A wrapper for sending WSGI server logging output to the Distil logger.
    """

    def __init__(self, LOG, level=logging.INFO):
        self.LOG = LOG
        self.level = level

    def write(self, msg):
        self.LOG.log(self.level, msg.rstrip("\n"))


def main():
    """
    Start a Distil Prometheus exporter WSGI server.
    """

    app = make_app(sys.argv[1:])
    CONF.log_opt_values(LOG, logging.INFO)
    eventlet.wsgi.server(
        eventlet.listen((CONF.exporter_addr, CONF.exporter_port), backlog=50),
        app,
        log=WritableLogger(LOG),
    )


if __name__ == "__main__":
    main()
