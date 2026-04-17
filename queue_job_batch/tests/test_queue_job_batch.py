# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests import common
from odoo.tools import mute_logger

from odoo.addons.mail.tools.discuss import Store

from ..controllers.main import RunJobBatchController


class TestQueueJobBatchStoreData(common.TransactionCase):
    def test_init_store_data_sets_batch_globals(self):
        batch_group = self.env.ref("queue_job_batch.group_queue_job_batch_user")
        self.env.user.write({"group_ids": [(4, batch_group.id)]})
        self.env["queue.job.batch"].sudo().create(
            {
                "name": "Batch",
                "user_id": self.env.user.id,
                "company_id": self.env.company.id,
                "is_read": False,
            }
        )

        store = Store()
        self.env["res.users"]._init_store_data(store)
        store_data = store.get_result()["Store"]

        self.assertTrue(store_data["hasQueueJobBatchUserGroup"])
        self.assertEqual(store_data["queueJobBatchCounter"], 1)
        self.assertIn("queueJobBatchCounterBusId", store_data)


class TestQueueJobBatchCreatePrivate(common.HttpCase):
    def test_queue_job_create_stays_private(self):
        self.authenticate("admin", "admin")
        with self.assertRaises(common.JsonRpcException) as cm, mute_logger("odoo.http"):
            self.make_jsonrpc_request(
                "/web/dataset/call_kw",
                params={
                    "model": "queue.job",
                    "method": "create",
                    "args": [],
                    "kwargs": {
                        "method_name": "write",
                        "model_name": "res.partner",
                        "uuid": "test",
                    },
                },
            )
        self.assertEqual("odoo.exceptions.AccessError", str(cm.exception))


class TestQueueJobBatchController(common.TransactionCase):
    def test_create_test_batch_jobs_links_jobs_to_batch(self):
        batch, job_uuids = RunJobBatchController._create_test_batch_jobs(
            self.env,
            size=3,
            description="Batch smoke test",
            batch_name="Batch smoke test",
        )

        jobs = self.env["queue.job"].search([("uuid", "in", job_uuids)])

        self.assertEqual(3, len(job_uuids))
        self.assertEqual(3, len(jobs))
        self.assertEqual(3, batch.job_count)
        self.assertEqual({batch.id}, set(jobs.mapped("job_batch_id").ids))
