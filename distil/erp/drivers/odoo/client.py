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


import odoorpc

from packaging.version import Version

from distil.erp.drivers.odoo.managers import credit
from distil.erp.drivers.odoo.managers import invoice_line
from distil.erp.drivers.odoo.managers import invoice
from distil.erp.drivers.odoo.managers import product
from distil.erp.drivers.odoo.managers import project


class Client(object):
    """A client class for managing the OpenStack Odoo ERP.

    :param hostname: Server hostname
    :type hostname: str
    :param database: Database name
    :type database: str
    :param username: Account username
    :type username: str
    :param password: Account password (or API key)
    :type password: str
    :param protocol: Communication protocol, defaults to ``jsonrpc``
    :type protocol: str, optional
    :param port: Access port, defaults to ``8069``
    :type port: int, optional
    :param version: Server version, defaults to ``None`` (auto-detect)
    :type version: str or None, optional
    """

    def __init__(
        self,
        hostname,
        database,
        username,
        password,
        protocol="jsonrpc",
        port=8069,
        version=None,
    ):
        self._odoo = odoorpc.ODOO(
            protocol=protocol,
            host=hostname,
            port=port,
            version=version,
        )
        self._odoo.login(database, username, password)
        self.credit = credit.CreditManager(self._odoo)
        """Project credit record manager."""
        self.invoice_line = invoice_line.InvoiceLineManager(self._odoo)
        """Invoice line manager."""
        self.invoice = invoice.InvoiceManager(self._odoo)
        """Invoice manager."""
        self.product = product.ProductManager(self._odoo)
        """ERP product manager."""
        self.project = project.ProjectManager(self._odoo)
        """OpenStack project manager."""

    @property
    def db(self):
        """The database management service."""
        return self._odoo.db

    @property
    def report(self):
        """The report management service."""
        return self._odoo.report

    @property
    def env(self):
        """The OdooRPC environment wrapper object.

        This allows interacting with models that do not have managers
        within this Odoo client.
        Usage is the same as on a native ``odoorpc.ODOO`` object.
        """
        return self._odoo.env

    @property
    def version(self):
        """The version of the server,
        as a comparable ``packaging.version.Version`` object.
        """
        return Version(self._odoo.version)
