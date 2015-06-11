#   Copyright 2015 OpenStack Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
"""The Extended Neutron VNIC Attributes API extension."""

from nova.api.openstack import extensions
from nova.api.openstack import wsgi
from nova.compute import utils as compute_utils
from nova.openstack.common import log as logging

ALIAS = "os-extended-networks"
authorize = extensions.soft_extension_authorizer('compute', 'v3:' + ALIAS)
LOG = logging.getLogger(__name__)


class ExtendedNeutronNetworksController(wsgi.Controller):
    def _extend_server(self, context, server, instance):
        key = "OS-EXT-NEU-NET"
        nw_info = compute_utils.get_nw_info_for_instance(instance)
        server[key] = nw_info

    @wsgi.extends
    def show(self, req, resp_obj, id):
        context = req.environ['nova.context']
        if authorize(context):
            server = resp_obj.obj['server']
            db_instance = req.get_db_instance(server['id'])
            # server['id'] is guaranteed to be in the cache due to
            # the core API adding it in its 'show' method.
            self._extend_server(context, server, db_instance)

    @wsgi.extends
    def detail(self, req, resp_obj):
        context = req.environ['nova.context']
        if authorize(context):
            servers = list(resp_obj.obj['servers'])
            for server in servers:
                db_instance = req.get_db_instance(server['id'])
                # server['id'] is guaranteed to be in the cache due to
                # the core API adding it in its 'detail' method.
                self._extend_server(context, server, db_instance)


class ExtendedNeutronNetworks(extensions.V3APIExtensionBase):
    """Extended Neutron Networks support."""

    name = "ExtendedNeutronNetworks"
    alias = ALIAS
    version = 1

    def get_controller_extensions(self):
        controller = ExtendedNeutronNetworksController()
        extension = extensions.ControllerExtension(self, 'servers', controller)
        return [extension]

    def get_resources(self):
        return []
