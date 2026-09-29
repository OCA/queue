# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from contextlib import closing
from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from ..controllers.main import RunJobController
from ..exception import JobError
from ..job import Job


class TestRunJobController(TransactionCase):
    def setUp(self):
        super().setUp()

        def _clean_queue_job():
            self.env["queue.job"].search([]).unlink()

        self.addCleanup(_clean_queue_job)

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

    @mute_logger("odoo.addons.queue_job.controllers.main")
    def test_runjob_on_fail_no_deadlock(self):
        """The on fail hook can write on the records the failed job wrote.

        The hook runs on another cursor, while the failed job's transaction
        is still open. Without rolling back the job's changes first, the hook
        waits for the job's lock, which is only released after the hook.
        """
        function = self.env.ref("queue_job.job_function_queue_job__test_job")
        function.on_fail_method = "_test_on_fail"
        # Use a committed record, so that the other cursor can see it
        partner = self.env.ref("base.partner_admin")
        job = self.env["queue.job"].with_delay()._test_job()

        # The job writes on the partner (locking it), then fails
        def failing_job():
            partner.name = "Written by job"
            partner.flush_recordset()
            raise JobError("Job failed")

        # The hook writes on the same partner from another cursor. Its changes
        # are rolled back on close, and the lock timeout avoids waiting forever.
        def on_fail(**kwargs):
            with closing(self.registry.cursor()) as other_cr:
                other_cr.execute("SET LOCAL lock_timeout = '2s'")
                other_cr.execute(
                    "UPDATE res_partner SET name = 'Written by hook' WHERE id = %s",
                    [partner.id],
                )

        with (
            self.assertRaises(JobError),
            patch(
                "odoo.addons.queue_job.models.queue_job.QueueJob._test_job",
                side_effect=failing_job,
            ),
            patch(
                "odoo.addons.queue_job.models.queue_job.QueueJob._test_on_fail",
                side_effect=on_fail,
            ) as mocked_hook,
            patch("odoo.addons.queue_job.job.Job.in_temporary_env") as mocked_temp_env,
        ):
            mocked_temp_env.return_value.__enter__.return_value = self.env
            RunJobController._runjob(self.env, job)
        self.assertEqual(mocked_hook.call_count, 1)

    def test_runjob_on_fail_not_configured(self):
        job = self.env["queue.job"].with_delay()._test_job(failure_rate=1)
        with (
            self.assertRaises(JobError),
            patch("odoo.addons.queue_job.job.Job.in_temporary_env") as mocked_temp_env,
            mute_logger("odoo.addons.queue_job.controllers.main"),
        ):
            mocked_temp_env.return_value.__enter__.return_value = self.env
            RunJobController._runjob(self.env, job)
        self.assertEqual(job.state, "failed")
