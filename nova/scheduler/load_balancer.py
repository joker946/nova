# Copyright (c) 2015 OpenStack Foundation
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

from oslo.config import cfg
from nova import db
from nova.i18n import _
from nova.openstack.common import log as logging


CONF = cfg.CONF
LOG = logging.getLogger(__name__)

lb_opts = [
    cfg.IntOpt('cpu_threshold',
               default=70,
               help='LoadBalancer CPU threshold, percent'),
    cfg.IntOpt('memory_threshold',
               default=70,
               help='LoadBalancer Memory threshold, percent'),
    cfg.FloatOpt('cpu_weight',
                 default=1.0,
                 help='CPU weight'),
    cfg.FloatOpt('memory_weight',
                 default=1.0,
                 help='Memory weight'),
    cfg.FloatOpt('io_weight',
                 default=1.0,
                 help='IO weight')
]

CONF.register_opts(lb_opts, 'loadbalancer')


class LoadBalancer(object):

    def __init__(self, *args, **kwargs):
        super(LoadBalancer, self).__init__(*args, **kwargs)

    def _normalize_params(self, instances):
        max_values = {}
        min_values = {}
        normalized_instances = []
        for instance in instances:
            for key in instance:
                if key != 'uuid':
                    if max_values.get(key):
                        if max_values[key] < instance[key]:
                            max_values[key] = instance[key]
                    else:
                        max_values[key] = instance[key]
                    if min_values.get(key):
                        if min_values[key] > instance[key]:
                            min_values[key] = instance[key]
                    else:
                        min_values[key] = instance[key]
        LOG.info(_(max_values))
        LOG.info(_(min_values))
        LOG.info(_(instances))
        for instance in instances:
            norm_ins = {}
            for key in instance:
                if key != 'uuid':
                    if len(instances) == 1 or max_values[key] == min_values[key]:
                        delta_key = 1
                    else:
                        delta_key = max_values[key] - min_values[key]
                    norm_ins[key] = float(
                        (instance[key] - min_values[key])) / float((delta_key))
                    norm_ins['uuid'] = instance['uuid']
            normalized_instances.append(norm_ins)
        return normalized_instances

    def _calculate_cpu(self, instance):
        delta_cpu_time = instance['cpu_time'] - instance['prev_cpu_time']
        delta_time = (instance['updated_at'] - instance['prev_updated_at'])\
            .seconds
        num_cpu = instance.instance['vcpus']
        cpu_load = float(delta_cpu_time) / \
            (float(delta_time) * (10 ** 7) * num_cpu)
        cpu_load = round(cpu_load, 2)
        return cpu_load

    def _choose_instance_to_migrate(self, instances, compute_nodes):
        instances_params = []
        for i in instances:
            if i.instance['vm_state'] == 'active':
                instance_weights = {'uuid': i.instance['uuid']}
                instance_weights['cpu'] = self._calculate_cpu(i)
                instance_weights['memory'] = i['mem']
                instance_weights['io'] = i[
                    'block_dev_iops'] - i['prev_block_dev_iops']
                instances_params.append(instance_weights)
        normalized_instances = self._normalize_params(instances_params)
        LOG.info(_(normalized_instances))

    def _step_threshold_function(self, context):
        compute_nodes = db.get_compute_node_stats(context)
        cpu_td = CONF.loadbalancer.cpu_threshold
        memory_td = CONF.loadbalancer.memory_threshold
        LOG.debug(_(cpu_td))
        LOG.debug(_(memory_td))
        for node in compute_nodes:
            cpu_used_percent = node['cpu_used_percent']
            memory_used = node['memory_total'] - node['memory_free']
            memory_used_percent = round(
                (float(memory_used) / float(node['memory_total'])) * 100.00, 0
            )
            LOG.debug(_(cpu_used_percent))
            LOG.debug(_(memory_used_percent))
            if cpu_used_percent > cpu_td or memory_used_percent > memory_td:
                instances = db.get_instances_stat(
                    context,
                    node.compute_node.hypervisor_hostname)
                self._choose_instance_to_migrate(instances, compute_nodes)

    def indicate_threshold(self, context):
        return self._step_threshold_function(context)
