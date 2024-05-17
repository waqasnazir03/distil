# Copyright (c) 2024 Catalyst Cloud Ltd.
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

from distil.erp.drivers.odoo.managers import base


class Project(base.RecordBase):
    def __init__(self, odoo, obj):
        # NOTE(callumdickinson): Explicitly define attributes,
        # to make them visible when using IDE or static type checking tools,
        # but also ensure they raise `AttributeError` when not selected
        # by the user in queries.
        # Since we still need to support Python 2.7 (for now),
        # we cannot use dataclasses or other more modern ways of doing this.
        if "id" in obj:
            self.id = obj.pop("id")
            """ID of the OpenStack project within Odoo."""
        if "name" in obj:
            self.name = obj.pop("name")
            """OpenStack project name."""
        if "os_id" in obj:
            self.os_id = obj.pop("os_id")
            """OpenStack project ID."""
        super(Project, self).__init__(odoo, obj)


class ProjectManager(base.RecordManagerBase):
    def __init__(self, odoo):
        super(ProjectManager, self).__init__(
            odoo=odoo,
            env=odoo.env["openstack.project"],
            record_class=Project,
        )
