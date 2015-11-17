from nova import db
from nova import context
from nova.compute import vm_states


class Fakes(object):

    def __init__(self):
        self.services = [
            dict(host='host1', binary='nova-compute', topic='compute',
                 report_count=1, disabled=False),
            dict(host='host2', binary='nova-compute', topic='compute',
                 report_count=1, disabled=False)
        ]
        self.nodes = [
            dict(local_gb=1024, memory_mb=1024, vcpus=1, hypervisor_type="xen",
                 disk_available_least=None, free_ram_mb=512, vcpus_used=1,
                 free_disk_gb=512, local_gb_used=0, updated_at=None,
                 memory_mb_used=256, cpu_info="",
                 hypervisor_hostname='node1', host_ip='127.0.0.1',
                 hypervisor_version=0, numa_topology=None,
                 suspend_state='active', mac_to_wake=''),
            dict(local_gb=2048, memory_mb=2048, vcpus=2, hypervisor_type="xen",
                 disk_available_least=1024, free_ram_mb=1024, vcpus_used=2,
                 free_disk_gb=1024, local_gb_used=0, updated_at=None,
                 memory_mb_used=256, cpu_info="",
                 hypervisor_hostname='node2', host_ip='127.0.0.1',
                 hypervisor_version=0, numa_topology=None,
                 suspend_state='active', mac_to_wake='')
            ]
        self.stats = [
            dict(compute_id=1,
                 memory_total=self.nodes[0]['memory_mb'],
                 cpu_used_percent=15,
                 memory_used=self.nodes[0]['free_ram_mb']),
            dict(compute_id=2,
                 memory_total=self.nodes[1]['memory_mb'],
                 cpu_used_percent=15,
                 memory_used=self.nodes[1]['free_ram_mb'])
        ]
        self.instances = [
            dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1,
                 host='node1', node='node1', vm_state=vm_states.ACTIVE,
                 image_ref=1, reservation_id='r-fakeres', user_id='fake',
                 project_id='fake', instance_type_id=2, ami_launch_index=0,
                 uuid='xxx'),
            dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1,
                 host='node2', node='node2', vm_state=vm_states.ACTIVE,
                 image_ref=1, reservation_id='r-fakeres', user_id='fake',
                 project_id='fake', instance_type_id=2, ami_launch_index=0,
                 uuid='yyy'),
            dict(root_gb=512, ephemeral_gb=0, memory_mb=512, vcpus=1,
                 host='node1', node='node1', vm_state=vm_states.STOPPED,
                 image_ref=1, reservation_id='r-fakeres', user_id='fake',
                 project_id='fake', instance_type_id=2, ami_launch_index=0,
                 uuid='zzz')
        ]


class LbFakes(object):

    def _init_services(self):
        self.fakes = Fakes()
        self.service1 = db.service_create(context.get_admin_context(),
                                          self.fakes.services[0])
        self.service2 = db.service_create(context.get_admin_context(),
                                          self.fakes.services[1])
        self.fakes.nodes[0].update(service_id=self.service1['id'])
        self.fakes.nodes[1].update(service_id=self.service2['id'])

    def _add_compute_nodes(self):
        for pos, node in enumerate(self.fakes.nodes):
            node = db.compute_node_create(self.context, node)
            self.fakes.stats[pos]['compute_id'] = node['id']
        for instance in self.fakes.instances:
            db.instance_create(self.context, instance)
        db.compute_node_stats_upsert(self.context, dict(
            node=self.fakes.stats[0],
            instances=[
                dict(instance_uuid='xxx', cpu_time=123123123,
                     mem=512, prev_cpu_time=12000000, block_dev_iops=1000,
                     prev_block_dev_iops=1000)]))
        db.compute_node_stats_upsert(self.context, dict(
            node=self.fakes.stats[1],
            instances=[
                dict(instance_uuid='yyy', cpu_time=123123123,
                     mem=512, prev_cpu_time=12000000, block_dev_iops=1000,
                     prev_block_dev_iops=1000)]))

    def _add_compute_nodes_without_instances(self):
        for pos, node in enumerate(self.fakes.nodes):
            node = db.compute_node_create(self.context, node)
            self.fakes.stats[pos]['compute_id'] = node['id']
        db.compute_node_stats_upsert(self.context, dict(
            node=self.fakes.stats[0],
            instances=[]))
        db.compute_node_stats_upsert(self.context, dict(
            node=self.fakes.stats[1],
            instances=[]))

    def _add_compute_node(self):
        del self.fakes.nodes[1]
        for pos, node in enumerate(self.fakes.nodes):
            node = db.compute_node_create(self.context, node)
            self.fakes.stats[pos]['compute_id'] = node['id']
        db.compute_node_stats_upsert(self.context, dict(
            node=self.fakes.stats[0],
            instances=[]))
