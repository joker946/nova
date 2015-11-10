import mock

from nova import context
from nova import db
from nova import test
from nova.loadbalancer import utils
from nova.tests.loadbalancer import fakes


class StandartDeviationTestCase(test.TestCase):

    def setUp(self):
        super(StandartDeviationTestCase, self).setUp()
        self.context = context.get_admin_context()
        self.service1 = db.service_create(context.get_admin_context(),
                                          fakes.COMPUTE_SERVICES[0])
        self.service2 = db.service_create(context.get_admin_context(),
                                          fakes.COMPUTE_SERVICES[1])
        fakes.COMPUTE_NODES[0].update(dict(service_id=self.service1['id']))
        fakes.COMPUTE_NODES[1].update(dict(service_id=self.service2['id']))
        for node in fakes.COMPUTE_NODES:
            db.compute_node_create(self.context, node)
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
        cpu_threshold = 0.2
        mem_threshold = 0.2
        compute_nodes = utils.get_compute_node_stats(self.context)
        self.assertEqual(len(compute_nodes), 2)
