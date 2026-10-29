# Copyright 2022 Camptocamp SA (https://www.camptocamp.com).
# @author Iván Todorovich <ivan.todorovich@camptocamp.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.queue_job.exception import RetryableJobError


class TestQueueJob(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.cron = cls.env.ref("queue_job_cron_jobrunner.queue_job_cron")
        # Cleanup triggers just in case
        cls.env["ir.cron.trigger"].search([]).unlink()

    def assertTriggerAt(self, at, message=None):
        """Ensures a cron trigger is created at the given time"""
        return self.assertTrue(
            self.env["ir.cron.trigger"].search([("call_at", "=", at)]),
            message,
        )

    @freeze_time("2022-02-22 22:22:22")
    def test_queue_job_cron_trigger(self):
        """Test that ir.cron triggers are created for every queue.job"""
        job = self.env["res.partner"].with_delay().create({"name": "test"})
        job_record = job.db_record()
        self.assertTriggerAt(fields.Datetime.now(), "Trigger should've been created")
        job_record.eta = fields.Datetime.now() + timedelta(hours=1)
        self.assertTriggerAt(job_record.eta, "A new trigger should've been created")

    @mute_logger("odoo.addons.queue_job_cron_jobrunner.models.queue_job")
    def test_queue_job_process(self):
        """Test that jobs are processed by the queue job cron"""
        # Create some jobs
        job1 = self.env["res.partner"].with_delay().create({"name": "test"})
        job1_record = job1.db_record()
        job2 = self.env["res.partner"].with_delay().create(False)
        job2_record = job2.db_record()
        job3 = self.env["res.partner"].with_delay(eta=3600).create({"name": "Test"})
        job3_record = job3.db_record()
        # Run the job processing cron
        self.env["queue.job"]._job_runner(commit=False)
        # Check that the jobs were processed
        self.assertEqual(job1_record.state, "done", "Processed OK")
        self.assertEqual(job2_record.state, "failed", "Has errors")
        self.assertEqual(job3_record.state, "pending", "Still pending, because of eta")

    @freeze_time("2022-02-22 22:22:22")
    def test_queue_job_cron_trigger_enqueue_dependencies(self):
        """Test that ir.cron execution enqueue waiting dependencies"""
        delayable = self.env["res.partner"].delayable().create({"name": "test"})
        delayable2 = self.env["res.partner"].delayable().create({"name": "test2"})
        delayable.on_done(delayable2)
        delayable.delay()
        job_record = delayable._generated_job.db_record()
        job_record_depends = delayable2._generated_job.db_record()

        self.env["queue.job"]._job_runner(commit=False)

        self.assertEqual(job_record.state, "done", "Processed OK")
        # if the state is "waiting_dependencies", it means the "enqueue_waiting()"
        # step has not been done when the parent job has been done
        self.assertEqual(job_record_depends.state, "done", "Processed OK")

    def test_acquire_one_job_use_priority(self):
        with freeze_time("2024-01-01 10:01:01"):
            self.env["res.partner"].with_delay(priority=3).create({"name": "test"})

        with freeze_time("2024-01-01 10:02:01"):
            job = (
                self.env["res.partner"].with_delay(priority=1).create({"name": "test"})
            )

        with freeze_time("2024-01-01 10:03:01"):
            self.env["res.partner"].with_delay(priority=2).create({"name": "test"})

        self.assertEqual(self.env["queue.job"]._acquire_one_job(), job.db_record())

    def test_acquire_one_job_consume_the_oldest_first(self):
        with freeze_time("2024-01-01 10:01:01"):
            job = (
                self.env["res.partner"].with_delay(priority=30).create({"name": "test"})
            )

        with freeze_time("2024-01-01 10:02:01"):
            self.env["res.partner"].with_delay(priority=30).create({"name": "test"})

        with freeze_time("2024-01-01 10:03:01"):
            self.env["res.partner"].with_delay(priority=30).create({"name": "test"})

        self.assertEqual(self.env["queue.job"]._acquire_one_job(), job.db_record())

    def _run_retryable_job(self, seconds=None, retry_pattern=None):
        """Process a job raising RetryableJobError as the cron runner does"""
        if retry_pattern:
            self.env["queue.job.function"].create(
                {"name": "<res.partner>.create", "retry_pattern": retry_pattern}
            )
        job = self.env["res.partner"].with_delay().create({"name": "test"})
        job_record = job.db_record()
        partner_model = type(self.env["res.partner"])

        def create(self, vals_list):
            raise RetryableJobError("Try again later", seconds=seconds)

        with (
            freeze_time("2022-02-22 22:22:22"),
            patch.object(partner_model, "create", create),
        ):
            job_record._process(commit=False)
        self.assertEqual(job_record.state, "pending")
        self.assertEqual(job_record.retry, 1)
        return job_record

    def test_queue_job_retryable_error_seconds(self):
        """RetryableJobError(seconds=N) postpones the job by N seconds"""
        job_record = self._run_retryable_job(seconds=120)
        self.assertEqual(
            job_record.eta, fields.Datetime.to_datetime("2022-02-22 22:24:22")
        )

    def test_queue_job_retryable_error_retry_pattern(self):
        """Without seconds, the retry pattern of the job function applies"""
        job_record = self._run_retryable_job(retry_pattern={1: 300})
        self.assertEqual(
            job_record.eta, fields.Datetime.to_datetime("2022-02-22 22:27:22")
        )

    def test_queue_job_retryable_error_default(self):
        """Without seconds or retry pattern, the job is postponed by 5 seconds"""
        job_record = self._run_retryable_job()
        self.assertEqual(
            job_record.eta, fields.Datetime.to_datetime("2022-02-22 22:22:27")
        )
