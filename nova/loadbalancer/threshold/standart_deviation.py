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


from nova import db
from nova.i18n import _
from nova.loadbalancer.threshold import base
from nova.loadbalancer import utils
from nova.openstack.common import log as logging

from oslo.config import cfg

import math


lb_opts = [
    cfg.FloatOpt('standart_deviation_threshold_cpu',
                 default=0.05,
                 help='Standart Deviation Threshold'),
    cfg.FloatOpt('standart_deviation_threshold_memory',
                 default=0.3,
                 help='Standart Deviation Threshold')
]


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_opts(lb_opts, 'loadbalancer')


class Standart_Deviation(base.Base):

    def __init__(self):
        pass

    def _calculate_sd(self, hosts, param):
        mean = reduce(lambda res, x: res + hosts[x][param],
                      hosts, 0) / len(hosts)
        LOG.debug("Mean %(param)s: %(mean)f", {'mean': mean, 'param': param})
        variaton = float(reduce(
            lambda res, x: res + (hosts[x][param] - mean) ** 2,
            hosts, 0)) / len(hosts)
        sd = math.sqrt(variaton)
        LOG.debug("SD %(param)s: %(sd)f", {'sd': sd, 'param': param})
        return sd

    def indicate(self, context):
        cpu_threshold = CONF.loadbalancer.standart_deviation_threshold_cpu
        mem_threshold = CONF.loadbalancer.standart_deviation_threshold_memory
        compute_nodes = db.get_compute_node_stats(context)
        instances = []
        for node in compute_nodes:
            node_instances = db.get_instances_stat(
                context,
                node.compute_node.hypervisor_hostname)
            instances.extend(node_instances)
        host_loads = {}
        for instance in instances:
            cpu_util = utils.calculate_cpu(instance, compute_nodes)
            if host_loads.get(instance.instance['host'], None):
                host_loads[instance.instance['host']]['mem'] += instance['mem']
                host_loads[instance.instance['host']]['cpu'] += cpu_util
            else:
                host_loads[instance.instance['host']] = {}
                host_loads[instance.instance['host']]['mem'] = instance['mem']
                host_loads[instance.instance['host']]['cpu'] = cpu_util

        for node in compute_nodes:
            if node.compute_node.hypervisor_hostname in host_loads:
                host_loads[node.compute_node.hypervisor_hostname]['mem'] \
                    /= float(node.compute_node.memory_mb)
                host_loads[node.compute_node.hypervisor_hostname]['cpu'] \
                    /= 100.00
            else:
                host_loads[node.compute_node.hypervisor_hostname] = {}
                host_loads[node.compute_node.hypervisor_hostname]['mem'] = 0
                host_loads[node.compute_node.hypervisor_hostname]['cpu'] = 0
        LOG.debug(_(host_loads))
        ram_sd = self._calculate_sd(host_loads, 'mem')
        cpu_sd = self._calculate_sd(host_loads, 'cpu')
        if cpu_sd > cpu_threshold or ram_sd > mem_threshold:
            extra_info = {'cpu_overload': False}
            if cpu_sd > cpu_threshold:
                overloaded_host = sorted(host_loads,
                                         key=lambda x: host_loads[x]['cpu'],
                                         reverse=True)[0]
                extra_info['cpu_overload'] = True
            else:
                overloaded_host = sorted(host_loads,
                                         key=lambda x: host_loads[x]['mem'],
                                         reverse=True)[0]
            host = filter(
                lambda x:
                x.compute_node.hypervisor_hostname == overloaded_host,
                compute_nodes)[0]
            LOG.debug(_(host))
            return host, compute_nodes, extra_info
        return [], [], {}
