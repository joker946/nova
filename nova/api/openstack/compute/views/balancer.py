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

    _collection_name = "lbrules"

    def basic(self, request, rule):
        return {
            "rule": {
                "id": rule["id"],
                "type": rule["type"],
                "value": rule["value"]
            },
        }

    def show(self, request, rule):
        rule_dict = {
            "rule": {
                "id": rule["id"],
                "type": rule["type"],
                "value": rule["value"]
            },
        }

        return rule_dict

    def index(self, request, rules):
        """Return the 'index' view of rules."""
        return self._list_view(self.basic, request, rules)

    def detail(self, request, rules):
        """Return the 'detail' view of rules."""
        return self._list_view(self.show, request, rules)

    def _list_view(self, func, request, rules):
        """Provide a view for a list of rules."""
        rule_list = [func(request, rule)["rule"] for rule in rules]
        rules_dict = dict(rules=rule_list)

        return rules_dict
