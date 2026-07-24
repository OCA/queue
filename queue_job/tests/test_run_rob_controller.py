# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from ..controllers.main import RunJobController
from ..exception import JobError
from ..job import Job


class TestRunJobController(TransactionCase):
    def setUp(cls):
        super().setUp()

        def _clean_queue_job():
            cls.env["queue.job"].search([]).unlink()

        cls.addCleanup(_clean_queue_job)

    def test_get_failure_values(self):
        method = self.env["res.users"].mapped
        job = Job(method)
        ctrl = RunJobController()
        rslt = ctrl._get_failure_values(job, "info", Exception("zero", "one"))
        self.assertEqual(
            rslt, {"exc_info": "info", "exc_name": "Exception", "exc_message": "zero"}
        )

    def test_runjob_success(self):
        job = self.env["queue.job"].with_delay()._test_job()
        RunJobController._runjob(self.env, job)
        self.assertEqual(job.state, "done")
        self.assertEqual(job.db_record().state, "done")

    def test_runjob_on_fail(self):
        function = self.env.ref("queue_job.job_function_queue_job__test_job")
        function.on_fail_method = "_test_on_fail"
        job = self.env["queue.job"].with_delay()._test_job(failure_rate=1)
        with (
            self.assertRaises(JobError),
            patch(
                "odoo.addons.queue_job.models.queue_job.QueueJob._test_on_fail"
            ) as mocked_hook,
            patch("odoo.addons.queue_job.job.Job.in_temporary_env") as mocked_temp_env,
            mute_logger("odoo.addons.queue_job.controllers.main"),
        ):
            mocked_temp_env.return_value.__enter__.return_value = self.env
            RunJobController._runjob(self.env, job)
            self.assertEqual(job.state, "failed")
            self.assertEqual(mocked_hook.call_count, 1)
