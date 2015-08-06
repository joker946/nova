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
from nova.openstack.common import log as logging

from oslo.config import cfg

import math


lb_opts = [
    cfg.FloatOpt('standart_deviation_threshold',
                 default=0.3,
                 help='Standart Deviation Threshold')]


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_opts(lb_opts, 'loadbalancer')


class Standart_Deviation(base.Base):
    def __init__(self):
        pass

    def indicate(self, context):
        compute_nodes = db.get_compute_node_stats(context)
        instances = []
        for node in compute_nodes:
            node_instances = db.get_instances_stat(
                context,
                node.compute_node.hypervisor_hostname)
            instances.extend(node_instances)
        vms_ram = {}
        for instance in instances:
            if vms_ram.get(instance.instance['host'], None):
                vms_ram[instance.instance['host']] += instance['mem']
            else:
                vms_ram[instance.instance['host']] = instance['mem']
        for node in compute_nodes:
            if node.compute_node.hypervisor_hostname in vms_ram:
                vms_ram[node.compute_node.hypervisor_hostname] \
                    /= float(node.compute_node.memory_mb)
            else:
                vms_ram[node.compute_node.hypervisor_hostname] = 0
        mean = reduce(
            lambda res, x: res + vms_ram[x], vms_ram, 0) / len(vms_ram)
        LOG.debug(_(mean))
        LOG.debug(_(vms_ram))
        sigma = float(reduce(
            lambda res, x: res + (vms_ram[x] - mean) ** 2, vms_ram, 0)) \
            / len(vms_ram)
        standart_deviation = math.sqrt(sigma)
        LOG.debug(_(standart_deviation))
        if standart_deviation > CONF.loadbalancer.standart_deviation_threshold:
            overloaded_host = sorted(vms_ram, key=lambda x: vms_ram[x],
                                     reverse=True)[0]
            host = filter(
                lambda x:
                x.compute_node.hypervisor_hostname == overloaded_host,
                compute_nodes)[0]
            LOG.debug(_(host))
            return host, compute_nodes
        return [], []
