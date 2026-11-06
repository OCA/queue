# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from datetime import datetime
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
        self.assertEqual(job.retry, 1)
        self.assertEqual(job.max_retries, 5)
        self.assertEqual(job.state, "done")
        self.assertEqual(job.db_record().state, "done")

    def test_runjob_on_fail(self):
        function = self.env.ref("queue_job.job_function_queue_job__test_job")
        function.on_fail_method = "_test_on_fail"
        job = self.env["queue.job"].with_delay()._test_job(failure_rate=1)
        with (
            patch(
                "odoo.addons.queue_job.models.queue_job.QueueJob._test_on_fail"
            ) as mocked_hook,
            patch.object(self.env.cr, "commit") as mocked_commit,
            self.assertRaises(JobError),
            mute_logger("odoo.addons.queue_job.controllers.main"),
        ):
            RunJobController._runjob(self.env, job)
        self.assertEqual(job.state, "failed")
        self.assertEqual(mocked_commit.call_count, 1)
        self.assertEqual(mocked_hook.call_count, 1)

    @mute_logger("odoo.addons.queue_job.controllers.main")
    def test_runjob_on_fail_no_deadlock(self):
        """The on fail hook can write on the records the failed job wrote.

        The hook used to run on another cursor, it's not the case anymore.
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

        # The hook writes on the same partner. Its changes are rolled back on close,
        # and the lock timeout avoids waiting forever.
        def on_fail(**kwargs):
            self.env.cr.execute("SET LOCAL lock_timeout = '2s'")
            self.env.cr.execute(
                "UPDATE res_partner SET name = 'Written by hook' WHERE id = %s",
                [partner.id],
            )

        with (
            patch.object(self.env.cr, "commit") as mocked_commit,
            self.assertRaises(JobError),
            patch(
                "odoo.addons.queue_job.models.queue_job.QueueJob._test_job",
                side_effect=failing_job,
            ),
            patch(
                "odoo.addons.queue_job.models.queue_job.QueueJob._test_on_fail",
                side_effect=on_fail,
            ) as mocked_hook,
        ):
            RunJobController._runjob(self.env, job)
        self.assertEqual(mocked_commit.call_count, 1)
        self.assertEqual(mocked_hook.call_count, 1)

    def test_runjob_on_fail_not_configured(self):
        job = self.env["queue.job"].with_delay()._test_job(failure_rate=1)
        with (
            patch.object(self.env.cr, "commit") as mocked_commit,
            self.assertRaises(JobError),
            mute_logger("odoo.addons.queue_job.controllers.main"),
        ):
            RunJobController._runjob(self.env, job)
        self.assertEqual(job.retry, 1)
        self.assertEqual(job.eta, None)
        self.assertEqual(job.state, "failed")
        self.assertEqual(mocked_commit.call_count, 1)

    def test_runjob_retry_then_fail(self):
        retry_s = 8
        job = (
            self.env["queue.job"]
            .with_delay()
            ._test_job(failure_rate=1, failure_retry_seconds=retry_s)
        )
        # Try once
        with mute_logger("odoo.addons.queue_job.controllers.main"):
            RunJobController._runjob(self.env, job)
        eta_seconds = (job.eta - datetime.now()).total_seconds()
        self.assertEqual(job.state, "pending")
        self.assertEqual(job.retry, 1)
        self.assertEqual(job.max_retries, 5)
        self.assertAlmostEqual(eta_seconds, retry_s, places=0)

        # Retry 3 more times
        with mute_logger("odoo.addons.queue_job.controllers.main"):
            RunJobController._runjob(self.env, job)
            RunJobController._runjob(self.env, job)
            RunJobController._runjob(self.env, job)
        eta_seconds = (job.eta - datetime.now()).total_seconds()
        self.assertEqual(job.retry, 4)
        self.assertEqual(job.state, "pending")
        self.assertEqual(job.db_record().state, "pending")
        self.assertAlmostEqual(eta_seconds, retry_s, places=0)

        # And the 5th time, it fails
        with (
            patch.object(self.env.cr, "commit") as mocked_commit,
            self.assertRaises(JobError),
            mute_logger("odoo.addons.queue_job.controllers.main"),
        ):
            RunJobController._runjob(self.env, job)
        eta_seconds = (job.eta - datetime.now()).total_seconds()
        self.assertEqual(job.retry, 5)
        self.assertEqual(job.state, "failed")
        self.assertAlmostEqual(eta_seconds, retry_s, places=0)
        self.assertEqual(mocked_commit.call_count, 1)

    def test_runjob_retry_then_succeed(self):
        retry_s = 8
        job = (
            self.env["queue.job"]
            .with_delay()
            ._test_job(failure_rate=1, failure_retry_seconds=retry_s)
        )
        # Try 4 times
        with mute_logger("odoo.addons.queue_job.controllers.main"):
            RunJobController._runjob(self.env, job)
            RunJobController._runjob(self.env, job)
            RunJobController._runjob(self.env, job)
            RunJobController._runjob(self.env, job)
        eta_seconds = (job.eta - datetime.now()).total_seconds()
        self.assertEqual(job.retry, 4)
        self.assertEqual(job.max_retries, 5)
        self.assertEqual(job.state, "pending")
        self.assertAlmostEqual(eta_seconds, retry_s, places=0)

        # Then it succeeds, at last
        job.kwargs = {**job.kwargs, "failure_rate": 0}
        with mute_logger("odoo.addons.queue_job.controllers.main"):
            RunJobController._runjob(self.env, job)
        eta_seconds = (job.eta - datetime.now()).total_seconds()
        self.assertEqual(job.retry, 5)
        self.assertEqual(job.state, "done")
        self.assertEqual(job.db_record().state, "done")
        self.assertAlmostEqual(eta_seconds, retry_s, places=0)
