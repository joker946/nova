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
from nova.compute import api as compute_api
from nova.i18n import _
from nova.loadbalancer import utils as lb_utils
from nova.openstack.common import log as logging
from nova.openstack.common import importutils
from nova.scheduler import filters
from stevedore import driver


lb_opts = [
    cfg.StrOpt('threshold_function',
               default='standart_deviation',
               help='Threshold function'),
    cfg.FloatOpt('cpu_weight',
                 default=1.0,
                 help='CPU weight'),
    cfg.FloatOpt('memory_weight',
                 default=1.0,
                 help='Memory weight'),
    cfg.FloatOpt('io_weight',
                 default=1.0,
                 help='IO weight'),
    cfg.FloatOpt('compute_cpu_weight',
                 default=1.0,
                 help='CPU weight'),
    cfg.FloatOpt('compute_memory_weight',
                 default=1.0,
                 help='Memory weight'),
    cfg.ListOpt('load_balancer_default_filters',
                default=[
                    'RetryFilter',
                    'AvailabilityZoneFilter',
                    'RealRamFilter',
                    'ComputeFilter',
                    'ComputeCapabilitiesFilter',
                    'ImagePropertiesFilter',
                    'ServerGroupAntiAffinityFilter',
                    'ServerGroupAffinityFilter',
                ],
                help='Which filter class names to use for filtering hosts '
                'when not specified in the request.')
]

CONF = cfg.CONF
LOG = logging.getLogger(__name__)
CONF.register_opts(lb_opts, 'loadbalancer')
CONF.import_opt('scheduler_host_manager', 'nova.scheduler.driver')


SUPPORTED_THRESHOLD_FUNCTIONS = [
    'step_threshold',
    'standart_deviation'
]


def get_threshold_function(func_name):
    if func_name in SUPPORTED_THRESHOLD_FUNCTIONS:
        namespace = 'nova.loadbalancer.threshold'
        mgr = driver.DriverManager(namespace, func_name)
        return mgr.driver()
    raise Exception('Setted up function is not supported.')


class LoadBalancer(object):
    def __init__(self, *args, **kwargs):
        super(LoadBalancer, self).__init__(*args, **kwargs)
        self.host_manager = importutils.import_object(
            CONF.scheduler_host_manager)
        self.filter_handler = filters.HostFilterHandler()
        self.compute_api = compute_api.API()
        self.threshold_function = get_threshold_function(
            CONF.loadbalancer.threshold_function)

    def _weight_hosts(self, normalized_hosts):
        weighted_hosts = []
        compute_cpu_weight = CONF.loadbalancer.compute_cpu_weight
        compute_memory_weight = CONF.loadbalancer.compute_memory_weight
        for host in normalized_hosts:
            weighted_host = {'host': host['host']}
            cpu_used = host['cpu_used_percent']
            memory_used = host['memory_used']
            weight = compute_cpu_weight * cpu_used + \
                compute_memory_weight * memory_used
            weighted_host['weight'] = weight
            weighted_hosts.append(weighted_host)
        return sorted(weighted_hosts,
                      key=lambda x: x['weight'], reverse=False)

    def _weight_instances(self, normalized_instances, extra_info=None):
        weighted_instances = []
        cpu_weight = CONF.loadbalancer.cpu_weight
        if extra_info.get('k_cpu'):
            cpu_weight = extra_info['k_cpu']
        memory_weight = CONF.loadbalancer.memory_weight
        io_weight = CONF.loadbalancer.io_weight
        for instance in normalized_instances:
            weighted_instance = {'uuid': instance['uuid']}
            weight = cpu_weight * instance['cpu'] + \
                memory_weight * instance['memory'] + \
                io_weight * instance['io']
            weighted_instance['weight'] = weight
            weighted_instances.append(weighted_instance)
        return sorted(weighted_instances,
                      key=lambda x: x['weight'], reverse=False)

    def _choose_instance_to_migrate(self, instances, extra_info=None):
        instances_params = []
        for i in instances:
            if i.instance['task_state'] != 'migrating' and i['prev_cpu_time']:
                instance_weights = {'uuid': i.instance['uuid']}
                instance_weights['cpu'] = lb_utils.calculate_cpu(i)
                instance_weights['memory'] = i['mem']
                instance_weights['io'] = i[
                    'block_dev_iops'] - i['prev_block_dev_iops']
                instances_params.append(instance_weights)
        LOG.debug(_(instances_params))
        normalized_instances = lb_utils.normalize_params(instances_params)
        LOG.info(_(normalized_instances))
        if extra_info.get('cpu_overload'):
            normalized_instances = filter(lambda x: x['memory'] == 0,
                                          normalized_instances)
            extra_info['k_cpu'] = -1
        weighted_instances = self._weight_instances(normalized_instances,
                                                    extra_info)
        LOG.info(_(weighted_instances))
        chosen_instance = weighted_instances[0]
        chosen_instance['resources'] = filter(
            lambda x: x['uuid'] == chosen_instance['uuid'],
            instances_params)[0]
        return chosen_instance

    def _choose_host_to_migrate(self, context, chosen_instance, nodes):
        filter_properties = lb_utils.build_filter_properties(context,
                                                             chosen_instance,
                                                             nodes)
        classes = self.host_manager.choose_host_filters(
            CONF.loadbalancer.load_balancer_default_filters)
        hosts = self.host_manager.get_all_host_states(context)
        filtered = self.filter_handler.get_filtered_objects(classes,
                                                            hosts,
                                                            filter_properties)
        nodes = filter_properties['nodes']
        for n in nodes:
            del n['memory_total']
        filtered_nodes = [
            n for n in nodes
            for host in filtered if n['host'] == host.hypervisor_hostname]
        normalized_hosts = lb_utils.normalize_params(filtered_nodes, 'host')
        weighted_hosts = self._weight_hosts(normalized_hosts)
        return weighted_hosts[0]

    def _balancer(self, context):
        node, nodes, extra_info = self.threshold_function.indicate(context)
        if node:
            instances = db.get_instances_stat(
                context,
                node.compute_node.hypervisor_hostname)
            chosen_instance = self._choose_instance_to_migrate(instances,
                                                               extra_info)
            LOG.debug(_(chosen_instance))
            chosen_host = self._choose_host_to_migrate(context,
                                                       chosen_instance,
                                                       nodes)
            selected_pair = {chosen_host['host']: chosen_instance['uuid']}
            LOG.debug(_(selected_pair))
            if node.compute_node.hypervisor_hostname == chosen_host['host']:
                LOG.debug("Source host is optimal."
                          " Live Migration will not be perfomed.")
                return
            instance = lb_utils.get_instance_object(context,
                                                    chosen_instance['uuid'])
            self.compute_api.live_migrate(lb_utils.get_context(), instance,
                                          False, False, chosen_host['host'])
            db.instance_cpu_time_update(
                context,
                {'instance_uuid': chosen_instance['uuid']})

    def indicate_threshold(self, context):
        return self._balancer(context)
