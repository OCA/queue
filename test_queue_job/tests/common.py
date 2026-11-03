# Copyright 2016-2019 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo.tests import common

from odoo.addons.queue_job.job import Job


class JobCommonCase(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.queue_job = self.env["queue.job"]
        self.user = self.env["res.users"]
        self.method = self.env["test.queue.job"].testing_method

    def _create_job(self):
        test_job = Job(self.method)
        test_job.store()
        stored = Job.db_record_from_uuid(self.env, test_job.uuid)
        self.assertEqual(len(stored), 1)
        return stored

    def _get_demo_job(self, uuid):
        # job created during load of demo data
        job = self.env["queue.job"].search([("uuid", "=", uuid)], limit=1)
        self.assertTrue(
            job,
            f"Demo data queue job {uuid!r} should be loaded in order "
            "to make this test work",
        )
        return job

    def is_job_locked(self, job, cr=None):
        lock_query = (
            "SELECT 1 FROM queue_job WHERE uuid = %s FOR NO KEY UPDATE SKIP LOCKED"
        )
        with self.env.registry.cursor() as cr:
            cr.execute(lock_query, [job.uuid])
            if not cr.fetchone():
                return True
        return False
