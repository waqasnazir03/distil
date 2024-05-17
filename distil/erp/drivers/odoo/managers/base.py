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

from packaging.version import Version


class RecordBase(object):
    def __init__(self, odoo, obj):
        self._odoo = odoo
        # NOTE(callumdickinson): Fallback for selected fields that were
        # not explicitly assigned by the implementing record class.
        # Set any remaining fields as object attributes.
        # They will not be visible in IDEs and static type checkers,
        # but they will be usable in code all the same.
        for key, value in obj.iteritems():
            setattr(self, key, value)

    def __str__(self):
        return "{}({})".format(
            type(self).__name__,
            ", ".join(
                (
                    "{}={}".format(k, repr(v))
                    for k, v in vars(self).iteritems()
                ),
            ),
        )

    def __repr__(self):
        return str(self)


class RecordManagerBase(object):
    def __init__(self, odoo, env, record_class, default_fields=None):
        self._odoo = odoo
        self._env = env
        self._record_class = record_class
        self._default_fields = default_fields

    @property
    def _odoo_version(self):
        return Version(self._odoo.version)

    def get(self, ids, fields=None, as_dict=False):
        """Get one or more specific records by ID.

        By default all fields available on the record model
        will be selected, but this can be filtered using the
        ``fields`` parameter.

        Use the ``as_dict`` parameter to return records as ``dict``
        objects, instead of record objects.

        :param ids: Record ID, or list of record IDs
        :type ids: str or Collection[str]
        :param fields: Fields to select, defaults to ``None`` (select all)
        :type fields: Iterable[str] or None, optional
        :param as_dict: Return records as dictionaries, defaults to ``False``
        :type as_dict: bool, optional
        :return: List of records
        :rtype: list[Record] or list[dict[str, Any]]
        """
        objs = (
            {
                self._get_local_field(field): value
                for field, value in obj.iteritems()
            }
            for obj in self._env.read(
                ids,
                fields=(
                    [
                        self._get_remote_field(field) for field in (
                            fields or self._default_fields
                        )
                    ]
                    if fields or self._default_fields
                    else None
                ),
            )
        )
        if as_dict:
            return list(objs)
        return [self._record_class(self._odoo, obj) for obj in objs]

    def list(
        self,
        filters=None,
        fields=None,
        order=None,
        as_ids=False,
        as_dict=False,
    ):
        """Query the ERP for records, optionally defining
        filters to constrain the search and other parameters,
        and return the results.

        :param filters: Filters to query by, defaults to ``None`` (no filters)
        :type filters: Iterable[tuple[str, str, Any]] or None, optional
        :param fields: Fields to select, defaults to ``None`` (select all)
        :type fields: Iterable[str] or None, optional
        :param order: Order results by field name, defaults to ``None``
        :type order: str or None, optional
        :param as_ids: Return the record IDs only, defaults to ``False``
        :type as_ids: bool, optional
        :param as_dict: Return records as dictionaries, defaults to ``False``
        :type as_dict: bool, optional
        :return: List of records
        :rtype: list[Record] or list[dict[str, Any]] or list[str]
        """
        ids = self._env.search(
            (
                [
                    (self._get_remote_field(attr), cond, value)
                    for attr, cond, value in filters
                ]
                if filters
                else []
            ),
            order=order,
        )
        if as_ids:
            return ids
        if ids:
            return self.get(ids, fields=fields, as_dict=as_dict)
        return []

    def _get_remote_field(self, field):
        return field

    def _get_local_field(self, field):
        return field
