# Copyright 2022 Camptocamp SA (https://www.camptocamp.com).
# @author Iván Todorovich <ivan.todorovich@camptocamp.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime

from freezegun import freeze_time

from odoo import SUPERUSER_ID, api
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestQueueJob(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))
        self.cron = self.env.ref("queue_job_cron_jobrunner.queue_job_cron")
        self.env2 = api.Environment(self.env.registry.cursor(), SUPERUSER_ID, {})

        def cleanUp():
            self.env2.cr.close()

        self.addCleanup(cleanUp)

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
        self.assertEqual(self.cron.nextcall, datetime(2022, 2, 22, 22, 22, 22))

    @freeze_time("2022-02-22 22:22:22")
    def test_concurrent_cron_access(self):
        """to avoid to launch ir cron twice odoo add a lock
        while running task, if task take times to compute
        other users should be able to create new queue job
        at the same time
        """
        self.env2.cr.execute(
            """SELECT * FROM ir_cron WHERE id=%s FOR UPDATE NOWAIT""",
            (self.cron.id,),
            log_exceptions=False,
        )

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
        self.assertNotEqual(self.cron.nextcall, datetime(2022, 2, 22, 22, 22, 22))

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
