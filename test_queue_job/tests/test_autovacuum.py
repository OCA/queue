# Copyright 2019 Versada UAB
# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).

from datetime import datetime, timedelta

from .common import JobCommonCase


class TestQueueJobAutovacuum(JobCommonCase):
    def test_old_jobs_are_deleted_by_autovacuum(self):
        """Old jobs are deleted by the autovacuum."""
        date_done = datetime.now() - timedelta(
            days=self.queue_job._removal_interval + 1
        )
        stored = self._create_job()
        stored.write({"date_done": date_done})
        self.assertEqual(self.env["queue.job"]._gc_old_jobs(), (1, False))
        self.assertFalse(stored.exists())

    def test_old_cancelled_jobs_are_deleted_by_autovacuum(self):
        """Old cancelled jobs are deleted by the autovacuum."""
        date_cancelled = datetime.now() - timedelta(
            days=self.queue_job._removal_interval + 1
        )
        stored = self._create_job()
        stored.write({"state": "cancelled", "date_cancelled": date_cancelled})
        self.env["queue.job"]._gc_old_jobs()
        self.assertFalse(stored.exists())

    def test_autovacuum(self):
        # test default removal interval
        stored = self._create_job()
        date_done = datetime.now() - timedelta(days=29)
        stored.write({"date_done": date_done})
        self.env["queue.job"]._gc_old_jobs()
        self.assertEqual(
            len(self.env["queue.job"].search([("channel", "!=", False)])), 1
        )

        date_done = datetime.now() - timedelta(days=31)
        stored.write({"date_done": date_done})
        self.env["queue.job"]._gc_old_jobs()
        self.assertEqual(
            len(self.env["queue.job"].search([("channel", "!=", False)])), 0
        )

    def test_autovacuum_multi_channel(self):
        root_channel = self.env.ref("queue_job.channel_root")
        channel_60days = self.env["queue.job.channel"].create(
            {"name": "60days", "removal_interval": 60, "parent_id": root_channel.id}
        )
        date_done = datetime.now() - timedelta(days=31)
        job_root = self._create_job()
        job_root.write({"date_done": date_done})
        job_60days = self._create_job()
        job_60days.write(
            {"channel": channel_60days.complete_name, "date_done": date_done}
        )
        self.assertEqual(
            len(self.env["queue.job"].search([("channel", "!=", False)])), 2
        )
        self.env["queue.job"]._gc_old_jobs()
        self.assertEqual(
            len(self.env["queue.job"].search([("channel", "!=", False)])), 1
        )

        date_done = datetime.now() - timedelta(days=61)
        job_60days.write({"date_done": date_done})
        self.env["queue.job"]._gc_old_jobs()
        self.assertEqual(
            len(self.env["queue.job"].search([("channel", "!=", False)])), 0
        )

    def test_autovacuum_unknown_channel(self):
        """Old jobs of an unknown channel use the root channel's interval.

        Scenario:
            1. A job ran on a channel that no longer exists.
            2. It is done for one day longer than the root channel's interval.
        Expected:
            - The autovacuum deletes the job.
        """
        root_channel = self.env.ref("queue_job.channel_root")
        stored = self._create_job()
        stored.write(
            {
                "channel": "root.unknown",
                "date_done": datetime.now()
                - timedelta(days=root_channel.removal_interval + 1),
            }
        )
        self.env["queue.job"]._gc_old_jobs()
        self.assertFalse(stored.exists())

    def test_old_jobs_are_deleted_by_base_autovacuum_cron(self):
        """Old jobs are deleted by the base autovacuum cron."""
        date_done = datetime.now() - timedelta(
            days=self.queue_job._removal_interval + 1
        )
        stored = self._create_job()
        stored.write({"date_done": date_done})
        with self.enter_registry_test_mode():
            self.env.ref("base.autovacuum_job").method_direct_trigger()
        self.assertFalse(stored.exists())
