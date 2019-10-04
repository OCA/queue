# Copyright 2019 Versada UAB
# License AGPL-3 or later (https://www.gnu.org/licenses/agpl).

import datetime

from odoo.tests import common

from odoo.addons.queue_job.job import Job


class TestQueueJobAutovacuumCronJob(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.queue_job = self.env["queue.job"]
        self.method = self.env["test.queue.job"].testing_method
        self.cron_job = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")

    def test_old_jobs_are_deleted(self):
        """
        Old jobs are deleted by the autovacuum cron job.
        """
        test_job = Job(self.method)
        test_job.set_done(result="ok")
        test_job.date_done = datetime.datetime.now() - datetime.timedelta(
            days=self.queue_job._removal_interval + 1
        )
        test_job.store()

        self.cron_job.method_direct_trigger()

        self.assertFalse(test_job.db_record().exists())
