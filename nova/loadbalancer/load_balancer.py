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

import datetime
import re

from oslo.config import cfg
from nova import db
from nova import manager
from nova.openstack.common import log as logging
from nova.openstack.common import periodic_task
from stevedore import driver
from statistics import make_stats


lb_opts = [
    cfg.BoolOpt('enable_balancer',
                default=True,
                help='Turn on or turn off balance mechanism'),
    cfg.BoolOpt('enable_underload',
                default=False,
                help='Turn on or turn off underload mechanism'),
    cfg.StrOpt('threshold_class',
               default='standart_deviation',
               help='Threshold class'),
    cfg.StrOpt('balancer_class',
               default='classic',
               help='Balancer class'),
    cfg.StrOpt('underload_class',
               default='mean_underload',
               help='Underload class')
]

clear_opts = [
    cfg.IntOpt('utc_offset',
               default=10800,
               help='UTC offset in seconds'),
    cfg.IntOpt('ttl',
               default=300,
               help='Time To Live in seconds')
]

CONF = cfg.CONF
LOG = logging.getLogger(__name__)
CONF.register_opts(lb_opts, 'loadbalancer')
CONF.register_opts(clear_opts, 'loadbalancer_clear_stats')
CONF.import_opt('scheduler_host_manager', 'nova.scheduler.driver')


SUPPORTED_THRESHOLD_CLASSES = [
    'step_threshold',
    'standart_deviation'
]


SUPPORTED_BALANCER_CLASSES = [
    'classic',
    'minimizeSD'
]


SUPPORTED_UNDERLOAD_CLASSES = [
    'mean_underload'
]


def get_balancer_class(class_name):
    if class_name in SUPPORTED_BALANCER_CLASSES:
        namespace = 'nova.loadbalancer.balancer'
        mgr = driver.DriverManager(namespace, class_name)
        return mgr.driver()
    raise Exception('Setted up class is not supported.')


def get_threshold_class(class_name):
    if class_name in SUPPORTED_THRESHOLD_CLASSES:
        namespace = 'nova.loadbalancer.threshold'
        mgr = driver.DriverManager(namespace, class_name)
        return mgr.driver()
    raise Exception('Setted up class is not supported.')


def get_underload_class(class_name):
    if class_name in SUPPORTED_UNDERLOAD_CLASSES:
        namespace = 'nova.loadbalancer.underload'
        mgr = driver.DriverManager(namespace, class_name)
        return mgr.driver()
    raise Exception('Setted up class is not supported.')


class LoadBalancer(manager.Manager):
    def __init__(self, *args, **kwargs):
        super(LoadBalancer, self).__init__(service_name='loadbalancer',
                                           *args, **kwargs)
        self.threshold_class = get_threshold_class(
            CONF.loadbalancer.threshold_class)
        self.balancer_class = get_balancer_class(
            CONF.loadbalancer.balancer_class)
        self.underload_class = get_underload_class(
            CONF.loadbalancer.underload_class)

    def _clear_compute_stats(self, context):
        utc_offset = CONF.loadbalancer_clear_stats.utc_offset
        ttl = CONF.loadbalancer_clear_stats.ttl
        overall_time = utc_offset + ttl
        delta_time = datetime.datetime.now() - datetime.timedelta(
            seconds=overall_time)
        db.clear_compute_stats(context, delta_time)
        LOG.debug("Compute stats cleared")

    def check_string(self, string, template):
        pattern = re.compile(template)
        if pattern.match(string):
            return True
        return False

    def rules(self, context):
        # types = ['host', 'ha', 'az']
        rules = db.lb_rule_get_all(context)
        nodes_ha = db.get_compute_nodes_ha(context)
        for node in nodes_ha:
            for rule in rules:
                if rule['type'] == 'ha':
                    if self.check_string(node['ha'], rule['value']):
                        node['passes'] = rule['allow']
                if rule['type'] == 'host':
                    if self.check_string(node['host'], rule['value']):
                        node['passes'] = rule['allow']
                if rule['type'] == 'az':
                    if self.check_string(node['az'], rule['value']):
                        node['passes'] = rule['allow']
        LOG.debug(nodes_ha)

    def _balancer(self, context):
        make_stats()
        node, nodes, extra_info = self.threshold_class.indicate(context)
        # db.lb_rule_create(context, {'type': 'host',
        #                            'value': 'compute1.students.dev',
        #                            'allow': False})
        self.rules(context)
        if node and CONF.loadbalancer.enable_balancer:
            return self.balancer_class.balance(context,
                                               node=node,
                                               nodes=nodes,
                                               extra_info=extra_info)
        if not node and CONF.loadbalancer.enable_underload:
            self.underload_class.indicate(context, extra_info=extra_info)

    @periodic_task.periodic_task
    def indicate_threshold(self, context):
        return self._balancer(context)

    @periodic_task.periodic_task
    def clear_compute_stats(self, context):
        return self._clear_compute_stats(context)

    @periodic_task.periodic_task
    def check_is_all_vms_migrated(self, context):
        return self.underload_class.check_is_all_vms_migrated(context)
