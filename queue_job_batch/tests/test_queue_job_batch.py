from odoo.tests import SavepointCase


class TestQueueJobBatch(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.batch1 = cls.env["queue.job.batch"].get_new_batch("batch 1")
        cls.batch2 = cls.env["queue.job.batch"].get_new_batch("batch 2")

    def test_default_order(self):
        """we want latest batch on top of the notification list"""
        batches = self.env["queue.job.batch"].search(
            [("id", "in", (self.batch1 | self.batch2).ids)]
        )
        self.assertEqual(batches[0].name, "batch 2")
        self.assertEqual(batches[1].name, "batch 1")
