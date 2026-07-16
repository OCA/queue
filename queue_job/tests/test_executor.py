# Copyright 2026 QoQa Services SA (https://www.qoqa.ch)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from unittest import mock

from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from ..exception import JobError, RetryableJobError
from ..executor import JobExecutor
from ..job import DONE, FAILED, PENDING, STARTED, Job, JobStore


class TestJobExecutor(TransactionCase):
    def _create_enqueued_job(self, **kwargs):
        job = self.env["queue.job"].with_delay()._test_job(**kwargs)
        job.set_enqueued()
        JobStore(self.env).save(job)
        # acquire() reads the state with raw SQL: flush the ORM writes.
        # In production the state is written and committed by the jobrunner
        # on its own connection.
        self.env.flush_all()
        return job

    def test_acquire_marks_started_and_locks(self):
        job = self._create_enqueued_job()
        executor = JobExecutor(self.env, job.uuid)
        acquired = executor.acquire()
        self.assertEqual(acquired.uuid, job.uuid)
        self.assertEqual(acquired.state, STARTED)
        self.assertEqual(acquired.db_record(self.env).state, STARTED)

    def test_run_success(self):
        job = self._create_enqueued_job()
        executor = JobExecutor(self.env, job.uuid)
        executor.run()
        self.assertEqual(job.db_record(self.env).state, DONE)

    @mute_logger("odoo.addons.queue_job.executor")
    def test_acquire_missing_job(self):
        executor = JobExecutor(self.env, "not-existing-uuid")
        self.assertIsNone(executor.acquire())

    @mute_logger("odoo.addons.queue_job.executor")
    def test_acquire_wrong_state(self):
        """A job that is not enqueued cannot be acquired"""
        job = self.env["queue.job"].with_delay()._test_job()
        JobStore(self.env).save(job)  # pending
        executor = JobExecutor(self.env, job.uuid)
        self.assertIsNone(executor.acquire())
        self.assertEqual(job.db_record(self.env).state, PENDING)

    @mute_logger("odoo.addons.queue_job.executor")
    def test_run_job_failure(self):
        job = self._create_enqueued_job(failure_rate=1)
        executor = JobExecutor(self.env, job.uuid)

        acquired = executor.acquire()
        # try/except instead of assertRaises: Odoo's assertRaises wraps the
        # block in a savepoint, which would also roll back the recorded
        # failure state
        raised = None
        try:
            executor.run_job(acquired)
        except JobError as err:
            raised = err

        self.assertIsNotNone(raised)

        record = job.db_record(self.env)

        self.assertEqual(record.state, FAILED)
        self.assertTrue(record.exc_name)
        self.assertTrue(
            any(
                "Something bad happened" in (message.body or "")
                for message in record.message_ids
            )
        )

    def test_run_job_retryable(self):
        job = self._create_enqueued_job()
        executor = JobExecutor(self.env, job.uuid)
        acquired = executor.acquire()

        with mock.patch.object(
            Job, "perform", side_effect=RetryableJobError("try later", seconds=60)
        ):
            executor.run_job(acquired)

        record = job.db_record(self.env)

        self.assertEqual(record.state, PENDING)
        self.assertTrue(record.eta)

    def test_get_failure_values(self):
        job = self._create_enqueued_job()

        executor = JobExecutor(self.env, job.uuid)
        result = executor._get_failure_values("info", Exception("zero", "one"))
        self.assertEqual(
            result, {"exc_info": "info", "exc_name": "Exception", "exc_message": "zero"}
        )
