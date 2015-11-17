import contextlib
import mock
from nova.tests.loadbalancer import fakes
from nova import context
from nova import test
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
