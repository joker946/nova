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
from nova import objects
from nova import utils as nova_utils
from nova.loadbalancer.underload.base import Base
from nova.loadbalancer.balancer.minimizeSD import MinimizeSD
from nova.loadbalancer import utils
from nova.openstack.common import log as logging
from nova.compute import rpcapi as compute_api

from oslo.config import cfg

lb_opts = [
    cfg.FloatOpt('threshold_cpu',
                 default=0.05,
                 help='CPU Underload Threshold'),
    cfg.FloatOpt('threshold_memory',
                 default=0.05,
                 help='Memory Underload Threshold')
]


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_opts(lb_opts, 'loadbalancer_mean_underload')


class MeanUnderload(Base):
    def __init__(self):
        self.compute_rpc = compute_api.ComputeAPI()

    def indicate(self, context):
        cpu_max = CONF.loadbalancer_mean_underload.threshold_cpu
        memory_max = CONF.loadbalancer_mean_underload.threshold_memory
        compute_nodes = db.get_compute_node_stats(context, use_mean=True)
        instances = []
        for node in compute_nodes:
            node_instances = db.get_instances_stat(context,
                                                   node['hypervisor_hostname'])
            instances.extend(node_instances)
        compute_stats = utils.fill_compute_stats(instances, compute_nodes)
        host_loads = utils.calculate_host_loads(compute_nodes, compute_stats)
        for node in host_loads:
            memory = host_loads[node]['mem']
            cpu = host_loads[node]['cpu']
            if (cpu < cpu_max) and (memory < memory_max):
                # Underload is needed.
                LOG.debug('underload is needed')
                db.make_host_suspended(context, node)
                minim = MinimizeSD()
                minim.migrate_all_vms_from_host(context, node)
                return True

    def check_is_all_vms_migrated(self, context):
        suspended_nodes = db.get_compute_node_stats(context,
                                                    read_suspended='only')
        for node in suspended_nodes:
            active_migrations = objects.migration.MigrationList\
                .get_in_progress_by_host_and_node(context,
                                                  node['hypervisor_hostname'],
                                                  node['hypervisor_hostname'])
            if active_migrations:
                LOG.debug('There is some migrations is active state')
                return
            else:
                mac = db.get_mac_address_to_wake(context,
                                                 node['hypervisor_hostname'])
                if mac:
                    continue
                out, err = nova_utils.execute('arp', '-a', node['host_ip'])
                mac = out.split()[3]
                eth_device = out.split()[6]
                self.compute_rpc.suspend_host(context,
                                              node['hypervisor_hostname'],
                                              eth_device)
                db.compute_node_update(context, node['compute_id'],
                                       {'mac_to_wake': mac})
