import contextlib
import mock
from nova.tests.loadbalancer import fakes
from nova import context
from nova import exception
from nova import objects
from nova.objects.compute_node import ComputeNodeList
from nova import test
from nova import utils as nova_utils
from nova.loadbalancer.underload import mean_underload
from nova.loadbalancer.threshold.standart_deviation import Standart_Deviation


class MeanUnderloadTestCase(test.TestCase, fakes.LbFakes):

    def setUp(self):
        super(MeanUnderloadTestCase, self).setUp()
        self.context = context.get_admin_context()
        self.underload = mean_underload.MeanUnderload()

    def test_indicate(self):
        self._init_services()
        self.fakes.stats[0].update(memory_used=300)
        self.fakes.stats[1].update(memory_used=300)
        self._add_compute_nodes()
        node, nodes, extra_info = Standart_Deviation().indicate(self.context)
        with contextlib.nested(
            mock.patch.object(self.underload, '_indicate_unsuspend_host'),
            mock.patch.object(self.underload, 'suspend_host')
        ) as (mock_indicate, mock_suspend_host):
            self.underload.indicate(self.context, extra_info=extra_info)
            self.assertFalse(mock_suspend_host.called)
            self.assertTrue(mock_indicate.called)

    def test_indicate_single_node(self):
        self._init_services()
        self._add_compute_node()
        node, nodes, extra_info = Standart_Deviation().indicate(self.context)
        with(
            mock.patch.object(self.underload, '_indicate_unsuspend_host')
        ) as (mock_indicate):
            self.underload.indicate(self.context, extra_info=extra_info)
            mock_indicate.assert_called_once_with(self.context,
                                                  extra_info=extra_info)

    def test_indicate_underload_is_needed(self):
        self._init_services()
        self.fakes.stats[0].update(memory_used=1)
        self.fakes.stats[1].update(memory_used=400)
        self._add_compute_nodes()
        node, nodes, extra_info = Standart_Deviation().indicate(self.context)
        with(
            mock.patch.object(self.underload,
                              'suspend_host', return_value=True)
        ) as (mock_suspend_host):
            self.underload.indicate(self.context, extra_info=extra_info)
            mock_suspend_host.assert_called_once_with(self.context, 'node1')

    def test_suspend_node(self):
        self._init_services()
        self._add_compute_nodes()
        with (
            mock.patch.object(self.underload.minimizeSD,
                              'migrate_all_vms_from_host', return_value=True)
        ) as (mock_migrate):
            self.underload.suspend_host(self.context, 'node1')
            mock_migrate.assert_called_once_with(self.context, 'node1')

    def test_suspend_node_in_suspending_state(self):
        self._init_services()
        self.fakes.nodes[0].update(suspend_state='suspending')
        self._add_compute_nodes()
        self.assertRaises(exception.ComputeHostWrongState,
                          self.underload.suspend_host, self.context, 'node1')

    def test_unsuspend_host(self):
        self._init_services()
        self.fakes.nodes[0].update(dict(suspend_state='suspended',
                                        mac_to_wake='MAC'))
        self._add_compute_nodes()
        node = ComputeNodeList.get_by_hypervisor(self.context, 'node1')
        with (mock.patch.object(nova_utils, 'execute')
              ) as (mock_execute):
            self.underload.unsuspend_host(self.context, node[0])
            mock_execute.assert_called_once_with(
                'ether-wake',
                self.fakes.nodes[0]['mac_to_wake'],
                run_as_root=True)
        updated_node = ComputeNodeList.get_by_hypervisor(self.context, 'node1')
        self.assertEqual(updated_node[0]['suspend_state'], 'active')

    def test_unsuspend_host_with_raise(self):
        self._init_services()
        self._add_compute_nodes()
        node = ComputeNodeList.get_by_hypervisor(self.context, 'node1')
        self.assertRaises(exception.ComputeHostWrongState,
                          self.underload.unsuspend_host, self.context, node[0])

    def test_check_is_all_vms_migrated(self):
        self._init_services()
        self.fakes.nodes[0].update(dict(suspend_state='suspending',
                                        mac_to_wake='MAC'))
        self.fakes.instances[0].update(dict(host='node2', node='node2'))
        self.fakes.instances[2].update(dict(host='node2', node='node2'))
        self._add_compute_nodes()
        with contextlib.nested(
            mock.patch.object(objects.migration.MigrationList,
                              'get_in_progress_by_host_and_node',
                              return_value=[]),
            mock.patch.object(self.underload.compute_rpc,
                              'prepare_host_for_suspending',
                              return_value="NEW_MAC"),
            mock.patch.object(self.underload.compute_rpc,
                              'suspend_host')
                ) as (mock_migration_list, mock_prepare_host,
                      mock_suspend_host):
            self.underload.check_is_all_vms_migrated(self.context)
            updated_node = ComputeNodeList.get_by_hypervisor(self.context,
                                                             'node1')
            self.assertEqual(updated_node[0]['suspend_state'], 'suspended')

    def test_check_is_all_vms_migrated_with_active_migrations(self):
        self._init_services()
        self.fakes.nodes[0].update(dict(suspend_state='suspending',
                                        mac_to_wake='MAC'))
        self._add_compute_nodes()
        with contextlib.nested(
            mock.patch.object(objects.migration.MigrationList,
                              'get_in_progress_by_host_and_node',
                              return_value=[{'instance_uuid': 'xxx',
                                             'status': 'finished'}]),
            mock.patch.object(self.underload.minimizeSD, 'confirm_migration')
                ) as (mock_migration_list, mock_confirm):
            self.underload.check_is_all_vms_migrated(self.context)
            mock_confirm.assert_called_once_with(self.context, 'xxx')

    def test_check_is_all_vms_migrated_filled_host(self):
        self._init_services()
        self.fakes.nodes[0].update(dict(suspend_state='suspending',
                                        mac_to_wake='MAC'))
        self._add_compute_nodes()
        with contextlib.nested(
            mock.patch.object(objects.migration.MigrationList,
                              'get_in_progress_by_host_and_node',
                              return_value=[]),
            mock.patch.object(self.underload.minimizeSD,
                              'migrate_all_vms_from_host',
                              return_value=True),
                ) as (mock_migration_list, mock_migrate):
            self.underload.check_is_all_vms_migrated(self.context)
            mock_migrate.assert_called_once_with(
                self.context,
                self.fakes.nodes[0]['hypervisor_hostname'])
            node = ComputeNodeList.get_by_hypervisor(self.context, 'node1')[0]
            self.assertEqual(node['suspend_state'], 'suspending')

    def test_check_is_all_vms_migrated_unable_to_empty_host(self):
        self._init_services()
        self.fakes.nodes[0].update(dict(suspend_state='suspending',
                                        mac_to_wake='MAC'))
        self._add_compute_nodes()
        with contextlib.nested(
            mock.patch.object(objects.migration.MigrationList,
                              'get_in_progress_by_host_and_node',
                              return_value=[]),
            mock.patch.object(self.underload.minimizeSD,
                              'migrate_all_vms_from_host',
                              return_value=False),
                ) as (mock_migration_list, mock_migrate):
            self.underload.check_is_all_vms_migrated(self.context)
            mock_migrate.assert_called_once_with(
                self.context,
                self.fakes.nodes[0]['hypervisor_hostname'])
            node = ComputeNodeList.get_by_hypervisor(self.context, 'node1')[0]
            self.assertEqual(node['suspend_state'], 'active')
