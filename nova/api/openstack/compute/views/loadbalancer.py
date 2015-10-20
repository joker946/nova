# Copyright (c) 2015 Servionica, LLC
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


from nova.api.openstack import common


class ViewBuilder(common.ViewBuilder):

    _collection_name = "loadbalancer"

    def basic(self, request, node):
        return {
            "node": {
                "hypervisor_hostname": node["hypervisor_hostname"],
                "cpu_used_percent": node["cpu_used_percent"],
                "memory_total": node["memory_total"],
                "memory_used": node["memory_used"],
                "suspend_state": node["suspend_state"],
                "mac_to_wake": node["mac_to_wake"],
                "vcpus": node["vcpus"]
            },
        }

    def show(self, request, node):
        rule_dict = {
            "node": {
                "id": node["id"],
                "type": node["type"],
                "value": node["value"]
            },
        }

        return rule_dict

    def index(self, request, nodes):
        """Return the 'index' view of nodes."""
        return self._list_view(self.basic, request, nodes)

    def detail(self, request, nodes):
        """Return the 'detail' view of nodes."""
        return self._list_view(self.show, request, nodes)

    def _list_view(self, func, request, nodes):
        """Provide a view for a list of rules."""
        node_list = [func(request, node)["node"] for node in nodes]
        nodes_dict = dict(compute_nodes=node_list)

        return nodes_dict
