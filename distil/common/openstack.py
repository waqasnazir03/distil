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

from collections import defaultdict
import re

from ceilometerclient import client as ceilometerclient
from cinderclient.v2 import client as cinderclient
from cinderclient.exceptions import NotFound as CinderNotFound
from glanceclient import client as glanceclient
from gnocchiclient import client as gnocchiclient
from keystoneauth1.identity import v3
from keystoneauth1.exceptions import NotFound
from keystoneauth1 import session
from keystoneclient.v3 import client as ks_client
from novaclient import client as novaclient
from novaclient.exceptions import NotFound as NovaNotFound
from oslo_config import cfg

from distil.common import cache as distil_cache
from distil.common import general

CONF = cfg.CONF
KS_SESSION = None
cache = defaultdict(dict)
ROOT_DEVICE_PATTERN = re.compile('^/dev/(x?v|s|h)da1?$')


def _get_keystone_session():
    global KS_SESSION

    if not KS_SESSION:
        auth = v3.Password(
            auth_url=CONF.keystone_authtoken.auth_url,
            username=CONF.keystone_authtoken.username,
            password=CONF.keystone_authtoken.password,
            project_name=CONF.keystone_authtoken.project_name,
            user_domain_name=CONF.keystone_authtoken.user_domain_name,
            project_domain_name=CONF.keystone_authtoken.project_domain_name,
        )
        KS_SESSION = session.Session(auth=auth, verify=False)

    return KS_SESSION


def get_keystone_client():
    sess = _get_keystone_session()
    return ks_client.Client(session=sess)


def get_ceilometer_client():
    sess = _get_keystone_session()

    return ceilometerclient.get_client(
        '2',
        session=sess,
        region_name=CONF.keystone_authtoken.region_name
    )

def get_gnocchi_client():
    sess = _get_keystone_session()

    return gnocchiclient.Client(
        '1',
        session=sess,
        region_name=CONF.keystone_authtoken.region_name
    )


def get_cinder_client():
    sess = _get_keystone_session()

    return cinderclient.Client(
        session=sess,
        region_name=CONF.keystone_authtoken.region_name
    )


def get_glance_client():
    sess = _get_keystone_session()

    return glanceclient.Client(
        '2',
        session=sess,
        region_name=CONF.keystone_authtoken.region_name
    )


def get_nova_client():
    sess = _get_keystone_session()

    return novaclient.Client(
        '2',
        session=sess,
        region_name=CONF.keystone_authtoken.region_name
    )


@general.disable_ssl_warnings
def get_domain(domain):
    keystone = get_keystone_client()
    try:
        domain_obj = keystone.domains.get(domain)
    except NotFound:
        domains = keystone.domains.list(name=domain)
        if not domains:
            raise
        domain_obj = domains[0]

    return domain_obj


@general.disable_ssl_warnings
def get_projects(domains=None):
    keystone = get_keystone_client()
    if not domains:
        return [obj.to_dict() for obj in keystone.projects.list()]

    domain_objs = {}
    for domain in domains:
        domain_obj = get_domain(domain)
        domain_objs[domain_obj.id] = domain_obj

    projects = []

    for domain_obj in domain_objs.values():
        projects += [
            obj.to_dict() for obj in keystone.projects.list(domain=domain_obj)]
    return projects


@general.disable_ssl_warnings
@distil_cache.memoize
def get_regions():
    keystone = get_keystone_client()

    return keystone.regions.list()


@general.disable_ssl_warnings
def get_image(image_id):
    glance = get_glance_client()
    return glance.images.get(image_id)


@general.disable_ssl_warnings
def get_root_volume(instance_id):
    nova = get_nova_client()
    volumes = nova.volumes.get_server_volumes(instance_id)

    vol_id = None
    volume = None

    for vol in volumes:
        if ROOT_DEVICE_PATTERN.search(vol.device):
            vol_id = vol.volumeId
            break

    if vol_id:
        cinder = get_cinder_client()
        volume = cinder.volumes.get(vol_id)

    return volume


@general.disable_ssl_warnings
def get_flavor_name(flavor_id):
    if flavor_id not in cache["flavors"]:
        nova = get_nova_client()
        try:
            flavor_name = nova.flavors.get(flavor_id).name
        except NovaNotFound:
            return None
        cache["flavors"][flavor_id] = flavor_name
    return cache["flavors"][flavor_id]


@general.disable_ssl_warnings
def get_volume_type_for_volume(volume_id):
    if volume_id not in cache["volume_id_to_type"]:
        cinder = get_cinder_client()
        try:
            vol = cinder.volumes.get(volume_id)
        except CinderNotFound:
            return None
        cache["volume_id_to_type"][volume_id] = vol.volume_type
    return cache["volume_id_to_type"][volume_id]


@general.disable_ssl_warnings
def get_volume_type_name(volume_type):
    if volume_type not in cache["volume_types"]:
        cinder = get_cinder_client()
        try:
            vtype = cinder.volume_types.get(volume_type)
        except CinderNotFound:
            try:
                vtype = cinder.volume_types.find(name=volume_type)
            except CinderNotFound:
                return None
        cache["volume_types"][vtype.id] = vtype.name
        cache["volume_types"][vtype.name] = vtype.name
    return cache["volume_types"][volume_type]


@general.disable_ssl_warnings
def get_object_storage_url(project_id):
    ks = get_keystone_client()
    try:
        endpoint = ks.endpoints.list(
            service=ks.services.list(type="object-store")[0],
            interface="public",
            region=CONF.keystone_authtoken.region_name)[0]
        return endpoint.url % {'tenant_id': project_id}
    except KeyError:
        return None


@general.disable_ssl_warnings
def get_container_policy(project_id, container_name):
    sess = _get_keystone_session()
    url = get_object_storage_url(project_id)
    if url:
        try:
            resp = sess.head("%s/%s" % (url, container_name))
            if resp:
                return resp.headers.get('X-Storage-Policy')
        except NotFound:
            return None
    return None
