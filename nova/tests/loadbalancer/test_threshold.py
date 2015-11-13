from nova import context
from nova import test
from nova.loadbalancer.threshold import standart_deviation
from nova.loadbalancer.threshold import step_threshold
from nova.tests.loadbalancer import fakes


class StandartDeviationTestCase(test.TestCase, fakes.LbFakes):

    def setUp(self):
        super(StandartDeviationTestCase, self).setUp()
        self.sd = standart_deviation.Standart_Deviation()
        self.context = context.get_admin_context()

    def test_indicate(self):
        self._init_services()
        self._add_compute_nodes()
        result = self.sd.indicate(self.context)
        self.assertEqual(result[0], [])

    def test_indicate_without_compute_nodes(self):
        self.mox.StubOutWithMock(standart_deviation.LOG, 'warn')
        standart_deviation.LOG.warn("There is not any compute node stats"
                                    " in database. Skipping indicating.")
        self.mox.ReplayAll()
        result = self.sd.indicate(self.context)
        self.assertEqual(result, None)

    def test_indicate_with_cpu_overload(self):
        self._init_services()
        fakes.COMPUTE_STATS[0].update(cpu_used_percent=90)
        self._add_compute_nodes()
        result = self.sd.indicate(self.context)
        self.assertEqual(fakes.COMPUTE_NODES[0]['hypervisor_hostname'],
                         result[0]['hypervisor_hostname'])

    def test_indicate_with_memory_overload(self):
        self._init_services()
        fakes.COMPUTE_STATS[0].update(memory_used=1000)
        fakes.COMPUTE_STATS[1].update(memory_used=100)
        self._add_compute_nodes()
        result = self.sd.indicate(self.context)
        print result
        self.assertEqual(fakes.COMPUTE_NODES[0]['hypervisor_hostname'],
                         result[0]['hypervisor_hostname'])


class StepThresholdTestCase(test.TestCase, fakes.LbFakes):

    def setUp(self):
        super(StepThresholdTestCase, self).setUp()
        self.context = context.get_admin_context()
        self.step = step_threshold.Step_Threshold()

    def test_indicate(self):
        result = self.step.indicate(self.context)
        self.assertEqual(result[0], [])

    def test_indicate_with_cpu_overload(self):
        self._init_services()
        fakes.COMPUTE_STATS[0].update(cpu_used_percent=90)
        self._add_compute_nodes()
        result = self.step.indicate(self.context)
        self.assertEqual(result[0]['hypervisor_hostname'],
                         fakes.COMPUTE_NODES[0]['hypervisor_hostname'])

    def test_indicate_with_memory_overload(self):
        self._init_services()
        fakes.COMPUTE_STATS[0].update(memory_used=768)
        self._add_compute_nodes()
        result = self.step.indicate(self.context)
        self.assertEqual(result[0]['hypervisor_hostname'],
                         fakes.COMPUTE_NODES[0]['hypervisor_hostname'])
