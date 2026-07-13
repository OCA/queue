# Copyright 2026 QoQa Services SA (https://www.qoqa.ch)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo.tests.common import TransactionCase

from ..executor import JobExecutor
from ..job import Job


class TestJobExecutor(TransactionCase):
    def test_run_success(self):
        job = self.env["queue.job"].with_delay()._test_job()
        JobExecutor(self.env, job.uuid).run()
        self.assertEqual(job.state, "done")
        self.assertEqual(job.db_record().state, "done")

    def test_get_failure_values(self):
        method = self.env["res.users"].mapped
        job = Job(method)
        executor = JobExecutor(self.env, job.uuid)
        result = executor._get_failure_values("info", Exception("zero", "one"))
        self.assertEqual(
            result, {"exc_info": "info", "exc_name": "Exception", "exc_message": "zero"}
        )
