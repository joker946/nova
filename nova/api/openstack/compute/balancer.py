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


import webob

from nova import db
from nova.api.openstack.compute.views import balancer as balancer_views
from nova.api.openstack import wsgi
from nova.api.openstack import xmlutil
from nova.loadbalancer.underload.mean_underload import MeanUnderload
from nova import exception
from nova.i18n import _
from webob import exc


def make_flavor(elem, detailed=False):
    elem.set('id')
    elem.set('type')
    elem.set('value')

    xmlutil.make_links(elem, 'links')


rule_nsmap = {None: xmlutil.XMLNS_V11, 'atom': xmlutil.XMLNS_ATOM}


class RuleTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('rule', selector='rule')
        make_flavor(root, detailed=True)
        return xmlutil.MasterTemplate(root, 1, nsmap=rule_nsmap)


class MinimalRulesTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('rules')
        elem = xmlutil.SubTemplateElement(root, 'rule', selector='rules')
        make_flavor(elem)
        return xmlutil.MasterTemplate(root, 1, nsmap=rule_nsmap)


class RulesTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('rules')
        elem = xmlutil.SubTemplateElement(root, 'rule', selector='rules')
        make_flavor(elem, detailed=True)
        return xmlutil.MasterTemplate(root, 1, nsmap=rule_nsmap)


class Controller(wsgi.Controller):
    """Flavor controller for the OpenStack API."""

    _view_builder_class = balancer_views.ViewBuilder

    @wsgi.serializers(xml=MinimalRulesTemplate)
    def index(self, req):
        """Return all flavors in brief."""
        rules = self._get_rules(req)
        return self._view_builder.index(req, rules)

    @wsgi.serializers(xml=RulesTemplate)
    def detail(self, req):
        """Return all flavors in detail."""
        limited_flavors = self._get_flavors(req)
        req.cache_db_flavors(limited_flavors)
        return self._view_builder.detail(req, limited_flavors)

    @wsgi.serializers(xml=RuleTemplate)
    def show(self, req, id):
        """Return data about the given rule id."""
        try:
            context = req.environ['nova.context']
            # rule = flavors.get_flavor_by_flavor_id(id, ctxt=context)
            # req.cache_db_flavor(flavor)
        except exception.NotFound:
            raise webob.exc.HTTPNotFound()

        # return self._view_builder.show(req, flavor)

    @wsgi.response(204)
    def delete(self, req, id):
        context = req.environ['nova.context']
        """Destroys a server."""
        try:
            db.lb_rule_delete(context, id)
        except exception.NotFound:
            msg = _("Rule could not be found")
            raise exc.HTTPNotFound(explanation=msg)

    @wsgi.response(202)
    def create(self, req, body):
        context = req.environ['nova.context']
        rule = None
        if 'lb_rules' in body:
            rule = body['lb_rules']
            if not isinstance(rule['type'], unicode):
                msg = _("Invalid lbrule type provided.")
                raise exc.HTTPBadRequest(explanation=msg)
            if not isinstance(rule['value'], unicode):
                msg = _("Invalid lbrule value provided.")
                raise exc.HTTPBadRequest(explanation=msg)
            if not isinstance(rule['allow'], bool):
                msg = _("allow key should be bool type.")
                raise exc.HTTPBadRequest(explanation=msg)
            db.lb_rule_create(context, rule)
            return rule

    @wsgi.action('suspend_host')
    def suspend_host(self, req, body):
        context = req.environ['nova.context']
        host = body['suspend_host']['host']
        MeanUnderload.suspend_host(context, host)

    def _get_rules(self, req):
        """Helper function that returns a list of flavor dicts."""

        context = req.environ['nova.context']
        rules = db.lb_rule_get_all(context)
        return rules


def create_resource():
    return wsgi.Resource(Controller())
