from nova import context
from nova import db
from nova import test
from nova.loadbalancer.threshold import standart_deviation
from nova.tests.loadbalancer import fakes


class StandartDeviationTestCase(test.TestCase):

    def setUp(self):
        super(StandartDeviationTestCase, self).setUp()
        self.sd = standart_deviation.Standart_Deviation()
        self.context = context.get_admin_context()
        self.service1 = db.service_create(context.get_admin_context(),
                                          fakes.COMPUTE_SERVICES[0])
        self.service2 = db.service_create(context.get_admin_context(),
                                          fakes.COMPUTE_SERVICES[1])
        fakes.COMPUTE_NODES[0].update(dict(service_id=self.service1['id']))
        fakes.COMPUTE_NODES[1].update(dict(service_id=self.service2['id']))

    def _add_compute_nodes_to_db(self):
        for pos, node in enumerate(fakes.COMPUTE_NODES):
            node = db.compute_node_create(self.context, node)
            fakes.COMPUTE_STATS[pos]['compute_id'] = node['id']
        for instance in fakes.INSTANCES:
            db.instance_create(self.context, instance)
        db.compute_node_stats_upsert(self.context, dict(
            node=fakes.COMPUTE_STATS[0],
            instances=[
                dict(instance_uuid='xxx', cpu_time=123123123,
                     mem=512)]))
        db.compute_node_stats_upsert(self.context, dict(
            node=fakes.COMPUTE_STATS[1],
            instances=[
                dict(instance_uuid='yyy', cpu_time=123123123,
                     mem=512)]))

    def test_indicate(self):
        self._add_compute_nodes_to_db()
        result = self.sd.indicate(self.context)
        self.assertEqual(result[0], [])

    def test_indicate_without_compute_nodes(self):
        self.mox.StubOutWithMock(standart_deviation.LOG, 'debug')
        standart_deviation.LOG.debug("There is not any compute node stats"
                                     " in database. Skipping indicating.")
        self.mox.ReplayAll()
        result = self.sd.indicate(self.context)
        self.assertEqual(result, None)

    def test_indicate_with_overload(self):
        fakes.COMPUTE_STATS[0].update(cpu_used_percent=0.9)
        self._add_compute_nodes_to_db()
        result = self.sd.indicate(self.context)
        self.assertEqual(fakes.COMPUTE_NODES[1]['hypervisor_hostname'],
                         result[0]['hypervisor_hostname'])
