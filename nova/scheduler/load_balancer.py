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

from keystoneclient.v2_0 import client
from oslo.config import cfg
from nova import context as nova_context
from nova import db
from nova import image
from nova import objects
from nova.compute import api as compute_api
from nova.i18n import _
from nova.openstack.common import log as logging
from nova.openstack.common import importutils
from nova.scheduler import filters
from nova.scheduler import utils


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


glance_username = 'glance'
glance_password = 'glance'
tenant_name = 'service'
auth_url = 'http://controller1:5000/v2.0/'


class LoadBalancer(object):

    def __init__(self, *args, **kwargs):
        super(LoadBalancer, self).__init__(*args, **kwargs)
        self.host_manager = importutils.import_object(
            CONF.scheduler_host_manager)
        self.image_api = image.API()
        self.glance_creds = client.Client(username=glance_username,
                                          password=glance_password,
                                          tenant_name=tenant_name,
                                          auth_url=auth_url)
        self.filter_handler = filters.HostFilterHandler()
        self.compute_api = compute_api.API()

    def _normalize_params(self, params, k='uuid'):
        max_values = {}
        min_values = {}
        normalized_params = []
        for param in params:
            for key in param:
                if key != k:
                    if max_values.get(key):
                        if max_values[key] < param[key]:
                            max_values[key] = param[key]
                    else:
                        max_values[key] = param[key]
                    if min_values.get(key):
                        if min_values[key] > param[key]:
                            min_values[key] = param[key]
                    else:
                        min_values[key] = param[key]
        LOG.info(_(max_values))
        LOG.info(_(min_values))
        LOG.info(_(params))
        for param in params:
            norm_ins = {}
            for key in param:
                if key != k:
                    if len(params) == 1 or max_values[key] == min_values[key]:
                        delta_key = 1
                    else:
                        delta_key = max_values[key] - min_values[key]
                    norm_ins[key] = float(
                        (param[key] - min_values[key])) / float((delta_key))
                    norm_ins[k] = param[k]
            normalized_params.append(norm_ins)
        return normalized_params

    def _get_context(self):
        creds = self.glance_creds
        s_catalog = creds.service_catalog.catalog['serviceCatalog']
        ctx = nova_context.RequestContext(user_id=creds.user_id,
                                          is_admin=True,
                                          project_id=creds.project_id,
                                          user_name=creds.username,
                                          project_name=creds.project_name,
                                          roles=['admin'],
                                          auth_token=creds.auth_token,
                                          remote_address=None,
                                          service_catalog=s_catalog,
                                          request_id=None)
        return ctx

    def _get_image(self, image_uuid):
        ctx = self._get_context()
        return (self.image_api.get(ctx, image_uuid), ctx)

    def _get_instance_object(self, context, uuid):
        expected_attrs = ['info_cache', 'security_groups',
                          'system_metadata']
        return objects.Instance.get_by_uuid(context, uuid, expected_attrs)

    def _calculate_cpu(self, instance):
        LOG.debug(_(instance.instance['uuid']))
        delta_cpu_time = instance['cpu_time'] - instance['prev_cpu_time']
        delta_time = (instance['updated_at'] - instance['prev_updated_at'])\
            .seconds
        num_cpu = instance.instance['vcpus']
        if delta_time:
            cpu_load = float(delta_cpu_time) / \
                (float(delta_time) * (10 ** 7) * num_cpu)
            cpu_load = round(cpu_load, 2)
            return cpu_load
        return 0

    def _weight_hosts(self, normalized_hosts):
        weitghted_hosts = []
        for host in normalized_hosts:
            weighted_host = {'host': host['host']}
            cpu_used = host['cpu_used_percent']
            memory_used = host['memory_used']
            weight = CONF.loadbalancer.compute_cpu_weight * cpu_used + \
                CONF.loadbalancer.compute_memory_weight * memory_used
            weighted_host['weight'] = weight
            weitghted_hosts.append(weighted_host)
        return sorted(weitghted_hosts,
                      key=lambda x: x['weight'], reverse=False)

    def _weight_instances(self, normalized_instances):
        weighted_instances = []
        for instance in normalized_instances:
            weighted_instance = {'uuid': instance['uuid']}
            weight = CONF.loadbalancer.cpu_weight * instance['cpu'] + \
                CONF.loadbalancer.memory_weight * instance['memory'] + \
                CONF.loadbalancer.io_weight * instance['io']
            weighted_instance['weight'] = weight
            weighted_instances.append(weighted_instance)
        return sorted(weighted_instances,
                      key=lambda x: x['weight'], reverse=False)

    def _choose_instance_to_migrate(self, instances):
        instances_params = []
        for i in instances:
            if i.instance['task_state'] != 'migrating' and i['prev_cpu_time']:
                instance_weights = {'uuid': i.instance['uuid']}
                instance_weights['cpu'] = self._calculate_cpu(i)
                instance_weights['memory'] = i['mem']
                instance_weights['io'] = i[
                    'block_dev_iops'] - i['prev_block_dev_iops']
                instances_params.append(instance_weights)
        normalized_instances = self._normalize_params(instances_params)
        LOG.info(_(normalized_instances))
        weighted_instances = self._weight_instances(normalized_instances)
        LOG.info(_(weighted_instances))
        chosen_instance = weighted_instances[0]
        chosen_instance['resources'] = filter(
            lambda x: x['uuid'] == chosen_instance['uuid'],
            instances_params)[0]
        return chosen_instance

    def _build_filter_properties(self, context, chosen_instance, nodes):
        instance = self._get_instance_object(context, chosen_instance['uuid'])
        image, ctx = self._get_image(instance.get('image_ref'))
        req_spec = utils.build_request_spec(ctx, image, [instance])
        filter_properties = {'context': ctx}
        instance_type = req_spec.get('instance_type')
        project_id = req_spec['instance_properties']['project_id']
        instance_resources = chosen_instance['resources']
        dict_nodes = []
        for n in nodes:
            dict_node = {'memory_total': n['memory_total'],
                         'memory_used': n['memory_used'],
                         'cpu_used_percent': n['cpu_used_percent'],
                         'host': n.compute_node.hypervisor_hostname}
            dict_nodes.append(dict_node)
        filter_properties.update({'instance_type': instance_type,
                                  'request_spec': req_spec,
                                  'project_id': project_id,
                                  'instance_resources': instance_resources,
                                  'nodes': dict_nodes})
        LOG.debug(_(filter_properties))
        return filter_properties

    def _choose_host_to_migrate(self, context, chosen_instance, nodes):
        filter_properties = self._build_filter_properties(context,
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
        normalized_hosts = self._normalize_params(filtered_nodes, 'host')
        weighted_hosts = self._weight_hosts(normalized_hosts)
        return weighted_hosts[0]

    def _sd_threshold_function(self, context):
        # Standart Deviation function.
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
            vms_ram[node.compute_node.hypervisor_hostname] \
                /= float(node.compute_node.memory_mb)
        mean = reduce(
            lambda res, x: vms_ram[res] + vms_ram[x], vms_ram) / len(vms_ram)
        LOG.debug(_(mean))
        LOG.debug(_(vms_ram))
        standart_deviation = reduce(lambda res, x: res + ())
        return None, None

    def _step_threshold_function(self, context):
        compute_nodes = db.get_compute_node_stats(context)
        cpu_td = CONF.loadbalancer.cpu_threshold
        memory_td = CONF.loadbalancer.memory_threshold
        LOG.debug(_(cpu_td))
        LOG.debug(_(memory_td))
        for node in compute_nodes:
            cpu_used_percent = node['cpu_used_percent']
            memory_used = node['memory_used']
            memory_used_percent = round(
                (float(memory_used) / float(node['memory_total'])) * 100.00, 0
            )
            LOG.debug(_(cpu_used_percent))
            LOG.debug(_(memory_used_percent))
            if cpu_used_percent > cpu_td or memory_used_percent > memory_td:
                return node, compute_nodes
        return [], []

    def _balancer(self, context):
        node, nodes = self._sd_threshold_function(context)
        if node:
            instances = db.get_instances_stat(
                context,
                node.compute_node.hypervisor_hostname)
            chosen_instance = self._choose_instance_to_migrate(instances)
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
            instance = self._get_instance_object(context,
                                                 chosen_instance['uuid'])
            self.compute_api.live_migrate(self._get_context(), instance, False,
                                          False, chosen_host['host'])

    def indicate_threshold(self, context):
        return self._balancer(context)
