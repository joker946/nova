from nova.tests.loadbalancer import fakes
from nova import context
from nova import test
from nova.loadbalancer.balancer import minimizeSD
from nova.loadbalancer.threshold import standart_deviation


class MinimizeSDTestCase(test.TestCase, fakes.LbFakes):

    def setUp(self):
        super(MinimizeSDTestCase, self).setUp()
        self.context = context.get_admin_context()
        self.balancer = minimizeSD.MinimizeSD()

    def test_min_sd(self):
        self._init_services()
        self.fakes.stats[0].update(cpu_used_percent=90)
        self._add_compute_nodes()
        self.mox.StubOutWithMock(self.balancer, 'filter_hosts')
        self.mox.StubOutWithMock(self.balancer, 'migrate')
        self.balancer.filter_hosts(
            self.context, {'uuid': u'xxx', 'resources': {'memory': 512,
                                                         'uuid': 'xxx',
                                                         'io': 0, 'cpu': 0}},
            [{'memory_used': 512, 'cpu_used_percent': 90,
              'hypervisor_hostname': 'node1', 'compute_id': 1, 'vcpus': 1,
              'suspend_state': 'active', 'memory_total': 1024,
              'mac_to_wake': ''},
             {'memory_used': 1024, 'cpu_used_percent': 15,
              'hypervisor_hostname': 'node2', 'compute_id': 2, 'vcpus': 2,
              'suspend_state': 'active', 'memory_total': 2048,
              'mac_to_wake': ''}], host='node2').AndReturn((True, True))
        self.balancer.migrate(self.context, 'xxx', 'node2')
        self.mox.ReplayAll()
        result = standart_deviation.Standart_Deviation().indicate(self.context)
        self.balancer.min_sd(self.context, nodes=result[1])

    def test_min_sd_no_instances(self):
        self._init_services()
        self._add_compute_nodes_without_instances()
        self.mox.StubOutWithMock(minimizeSD.LOG, 'debug')
        minimizeSD.LOG.warn("Instances could not be found."
                            " Skipping balancing")
        self.mox.ReplayAll()
        result = standart_deviation.Standart_Deviation().indicate(self.context)
        self.balancer.min_sd(self.context, nodes=result[1])

    def test_migrate_all_vms_from_host(self):
        self._init_services()
        del self.fakes.instances[2]
        self._add_compute_nodes()
        self.mox.StubOutWithMock(self.balancer, 'filter_hosts')
        self.mox.StubOutWithMock(self.balancer, 'migrate')
        self.balancer.filter_hosts(
            self.context, {'uuid': u'xxx', 'resources': {'memory': 512,
                                                         'uuid': 'xxx',
                                                         'io': 0, 'cpu': 0}},
            [{'memory_used': 512, 'cpu_used_percent': 15,
              'hypervisor_hostname': 'node1', 'compute_id': 1, 'vcpus': 1,
              'suspend_state': 'active', 'memory_total': 1024,
              'mac_to_wake': ''},
             {'memory_used': 1024, 'cpu_used_percent': 15,
              'hypervisor_hostname': 'node2', 'compute_id': 2, 'vcpus': 2,
              'suspend_state': 'active', 'memory_total': 2048,
              'mac_to_wake': ''}], host='node2').AndReturn((True, True))
        self.balancer.migrate(self.context, 'xxx', hostname='node2')
        self.mox.ReplayAll()
        result = self.balancer.migrate_all_vms_from_host(self.context, 'node1')
        self.assertTrue(result)

    def test_migrate_all_vms_from_host_nothing_is_filtered(self):
        self._init_services()
        del self.fakes.instances[2]
        self._add_compute_nodes()
        self.mox.StubOutWithMock(self.balancer, 'filter_hosts')
        self.balancer.filter_hosts(
            self.context, {'uuid': u'xxx', 'resources': {'memory': 512,
                                                         'uuid': 'xxx',
                                                         'io': 0, 'cpu': 0}},
            [{'memory_used': 512, 'cpu_used_percent': 15,
              'hypervisor_hostname': 'node1', 'compute_id': 1, 'vcpus': 1,
              'suspend_state': 'active', 'memory_total': 1024,
              'mac_to_wake': ''},
             {'memory_used': 1024, 'cpu_used_percent': 15,
              'hypervisor_hostname': 'node2', 'compute_id': 2, 'vcpus': 2,
              'suspend_state': 'active', 'memory_total': 2048,
              'mac_to_wake': ''}], host='node2').AndReturn((False, False))
        self.mox.ReplayAll()
        result = self.balancer.migrate_all_vms_from_host(self.context, 'node1')
        self.assertFalse(result)

    def test_migrate_all_vms_from_host_shutdown_include(self):
        self._init_services()
        self._add_compute_nodes()
        self.mox.StubOutWithMock(self.balancer, 'migrate')
        self.mox.StubOutWithMock(self.balancer, 'filter_hosts')
        self.balancer.migrate(self.context, 'zzz', cold_migration=True)
        self.balancer.filter_hosts(
            self.context, {'uuid': u'xxx', 'resources': {'memory': 512,
                                                         'uuid': 'xxx',
                                                         'io': 0, 'cpu': 0}},
            [{'memory_used': 512, 'cpu_used_percent': 15,
              'hypervisor_hostname': 'node1', 'compute_id': 1, 'vcpus': 1,
              'suspend_state': 'active', 'memory_total': 1024,
              'mac_to_wake': ''},
             {'memory_used': 1024, 'cpu_used_percent': 15,
              'hypervisor_hostname': 'node2', 'compute_id': 2, 'vcpus': 2,
              'suspend_state': 'active', 'memory_total': 2048,
              'mac_to_wake': ''}], host='node2').AndReturn((True, True))
        self.balancer.migrate(self.context, 'xxx', hostname='node2')
        self.mox.ReplayAll()
        result = self.balancer.migrate_all_vms_from_host(self.context, 'node1')
        self.assertTrue(result)

    def test_migrate_all_vms_from_host_shutdown_only(self):
        self._init_services()
        self.fakes.instances[0].update(vm_state='stopped')
        self.fakes.instances[1].update(vm_state='stopped')
        self._add_compute_nodes()
        self.mox.StubOutWithMock(self.balancer, 'migrate')
        for uuid in ['zzz', 'xxx']:
            self.balancer.migrate(self.context, uuid,
                                  cold_migration=True).AndReturn(True)
        self.mox.ReplayAll()
        result = self.balancer.migrate_all_vms_from_host(self.context, 'node1')
        self.assertTrue(result)
