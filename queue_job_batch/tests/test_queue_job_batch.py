# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase

from odoo.addons.queue_job.exception import RetryableJobError


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

    def test_check_done(self):
        self.jobs[0].set_started()
        self.jobs[0].perform()
        self.jobs[0].set_done()
        self.jobs[0].store()
        with self.assertRaises(RetryableJobError):
            self.job_batch.check_done()
        self.jobs[1].set_started()
        self.jobs[1].perform()
        self.jobs[1].set_done()
        self.jobs[1].store()
        self.job_batch.check_done()
