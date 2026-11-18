# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class TestJobBatch(TransactionCase):
    def setUp(self):
        super().setUp()
        self.job_batch = self.env["queue.job.batch"].create(
            {
                "name": "test",
                "user_id": self.env.user.id,
            }
        )
        partners = self.env.ref("base.res_partner_1") + self.env.ref(
            "base.res_partner_2"
        )
        self.jobs = [
            p.with_context(job_batch=self.job_batch).with_delay()._get_complete_name()
            for p in partners
        ]
        self.assertEqual(len(self.job_batch.job_ids), len(self.jobs))

    def test_execution_time(self):
        self.assertEqual(self.job_batch.execution_time, 0)
        for job in self.jobs:
            job.set_started()
            job.perform()
            job.set_done()
            job.store()
            self.assertGreater(job.exec_time, 0)
        self.assertEqual(
            self.job_batch.execution_time,
            self.jobs[0].exec_time + self.jobs[1].exec_time,
        )
