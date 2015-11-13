from nova import db
from nova import context
from nova.compute import vm_states
from oslo.config import cfg

CONF = cfg.CONF


COMPUTE_SERVICES = [
    dict(host='host1', binary='nova-compute', topic='compute',
         report_count=1, disabled=False),
    dict(host='host2', binary='nova-compute', topic='compute',
         report_count=1, disabled=False)
]

COMPUTE_NODES = [
    dict(local_gb=1024, memory_mb=1024, vcpus=1, hypervisor_type="xen",
         disk_available_least=None, free_ram_mb=512, vcpus_used=1,
         free_disk_gb=512, local_gb_used=0, updated_at=None,
         memory_mb_used=256, cpu_info="",
         hypervisor_hostname='node1', host_ip='127.0.0.1',
         hypervisor_version=0, numa_topology=None, suspend_state='active',
         mac_to_wake=''),
    dict(local_gb=2048, memory_mb=2048, vcpus=2, hypervisor_type="xen",
         disk_available_least=1024, free_ram_mb=1024, vcpus_used=2,
         free_disk_gb=1024, local_gb_used=0, updated_at=None,
         memory_mb_used=256, cpu_info="",
         hypervisor_hostname='node2', host_ip='127.0.0.1',
         hypervisor_version=0, numa_topology=None, suspend_state='active',
         mac_to_wake='')
]

COMPUTE_STATS = [
    dict(compute_id=1,
         memory_total=COMPUTE_NODES[0]['memory_mb'],
         cpu_used_percent=15,
         memory_used=COMPUTE_NODES[0]['free_ram_mb']),
    dict(compute_id=2,
         memory_total=COMPUTE_NODES[1]['memory_mb'],
         cpu_used_percent=15,
         memory_used=COMPUTE_NODES[1]['free_ram_mb'])
]

INSTANCES = [
    dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1, uuid='xxx',
         host='node1', node='node1', vm_state=vm_states.ACTIVE,
         image_ref=1, reservation_id='r-fakeres', user_id='fake',
         project_id='fake', instance_type_id=2, ami_launch_index=0),
    dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1, uuid='yyy',
         host='node2', node='node2', vm_state=vm_states.ACTIVE,
         image_ref=1, reservation_id='r-fakeres', user_id='fake',
         project_id='fake', instance_type_id=2, ami_launch_index=0),
    dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1, uuid='zzz',
         host='node1', node='node1', vm_state=vm_states.STOPPED,
         image_ref=1, reservation_id='r-fakeres', user_id='fake',
         project_id='fake', instance_type_id=2, ami_launch_index=0)
]


class LbFakes(object):

    def _init_services(self):
        self.service1 = db.service_create(context.get_admin_context(),
                                          COMPUTE_SERVICES[0])
        self.service2 = db.service_create(context.get_admin_context(),
                                          COMPUTE_SERVICES[1])
        COMPUTE_NODES[0].update(dict(service_id=self.service1['id']))
        COMPUTE_NODES[1].update(dict(service_id=self.service2['id']))

    def _add_compute_nodes(self):
        for pos, node in enumerate(COMPUTE_NODES):
            node = db.compute_node_create(self.context, node)
            COMPUTE_STATS[pos]['compute_id'] = node['id']
        for instance in INSTANCES:
            db.instance_create(self.context, instance)
        db.compute_node_stats_upsert(self.context, dict(
            node=COMPUTE_STATS[0],
            instances=[
                dict(instance_uuid='xxx', cpu_time=123123123,
                     mem=512, prev_cpu_time=12000000, block_dev_iops=1000,
                     prev_block_dev_iops=1000)]))
        db.compute_node_stats_upsert(self.context, dict(
            node=COMPUTE_STATS[1],
            instances=[
                dict(instance_uuid='yyy', cpu_time=123123123,
                     mem=512, prev_cpu_time=12000000, block_dev_iops=1000,
                     prev_block_dev_iops=1000)]))

    def _add_compute_nodes_without_instances(self):
        for pos, node in enumerate(COMPUTE_NODES):
            node = db.compute_node_create(self.context, node)
            COMPUTE_STATS[pos]['compute_id'] = node['id']
        db.compute_node_stats_upsert(self.context, dict(
            node=COMPUTE_STATS[0],
            instances=[]))
        db.compute_node_stats_upsert(self.context, dict(
            node=COMPUTE_STATS[1],
            instances=[]))
