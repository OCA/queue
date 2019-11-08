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
        self.env["queue.job.function"]._register_job(
            self.env["test.queue.job"], self.method
        )

    def _create_job(self):
        test_job = Job(self.method)
        test_job.store()
        stored = Job.db_record_from_uuid(self.env, test_job.uuid)
        self.assertEqual(len(stored), 1)
        return stored
