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
        sd_threshold = CONF.loadbalancer.standart_deviation_threshold
        compute_nodes = db.get_compute_node_stats(context)
        instances = []
        for node in compute_nodes:
            node_instances = db.get_instances_stat(
                context,
                node.compute_node.hypervisor_hostname)
            instances.extend(node_instances)
        vms_ram = {}
        for instance in instances:
            cpu_util = utils.calculate_cpu(instance, compute_nodes)
            if vms_ram.get(instance.instance['host'], None):
                vms_ram[instance.instance['host']]['mem'] += instance['mem']
                vms_ram[instance.instance['host']]['cpu'] += cpu_util
            else:
                vms_ram[instance.instance['host']] = {}
                vms_ram[instance.instance['host']]['mem'] = instance['mem']
                vms_ram[instance.instance['host']]['cpu'] = cpu_util

        for node in compute_nodes:
            if node.compute_node.hypervisor_hostname in vms_ram:
                vms_ram[node.compute_node.hypervisor_hostname]['mem'] \
                    /= float(node.compute_node.memory_mb)
                vms_ram[node.compute_node.hypervisor_hostname]['cpu'] \
                    /= 100.00
            else:
                vms_ram[node.compute_node.hypervisor_hostname]['mem'] = 0
                vms_ram[node.compute_node.hypervisor_hostname]['cpu'] = 0
        mean_ram = reduce(
            lambda res, x: res + vms_ram[x]['mem'], vms_ram, 0) / len(vms_ram)
        mean_cpu = reduce(
            lambda res, x: res + vms_ram[x]['cpu'], vms_ram, 0) / len(vms_ram)
        LOG.debug(_(mean_ram))
        LOG.debug(_(mean_cpu))
        variance_ram = float(reduce(
            lambda res, x: res + (vms_ram[x]['mem'] - mean_ram) ** 2,
            vms_ram, 0)) / len(vms_ram)
        variance_cpu = float(reduce(
            lambda res, x: res + (vms_ram[x]['cpu'] - mean_cpu) ** 2,
            vms_ram, 0)) / len(vms_ram)
        ram_sd = math.sqrt(variance_ram)
        cpu_sd = math.sqrt(variance_cpu)
        LOG.debug(_(cpu_sd))
        LOG.debug(_(ram_sd))
        if cpu_sd > sd_threshold or ram_sd > sd_threshold:
            overloaded_host = sorted(vms_ram, key=lambda x: vms_ram[x]['mem'],
                                     reverse=True)[0]
            host = filter(
                lambda x:
                x.compute_node.hypervisor_hostname == overloaded_host,
                compute_nodes)[0]
            LOG.debug(_(host))
            return host, compute_nodes
        return [], []
