# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from contextlib import closing
from datetime import datetime, timedelta

from odoo.tests import tagged

from odoo.addons.queue_job.job import Job
from odoo.addons.queue_job.jobrunner.runner import Database

from .common import JobCommonCase


@tagged("post_install", "-at_install")
class TestRequeueDeadJob(JobCommonCase):
    def get_locks(self, uuid, cr=None):
        """
        Retrieve lock rows
        """
        if cr is None:
            cr = self.env.cr

        cr.execute(
            """
            SELECT
                queue_job_id
            FROM
                queue_job_lock
            WHERE
                queue_job_id IN (
                    SELECT
                        id
                    FROM
                        queue_job
                    WHERE
                        uuid = %s
                )
            FOR NO KEY UPDATE SKIP LOCKED
            """,
            [uuid],
        )

        return cr.fetchall()

    def test_add_lock_record(self):
        queue_job = self._get_demo_job("test_started_job")
        self.assertEqual(len(queue_job), 1)
        job_obj = Job.load(self.env, queue_job.uuid)

        job_obj.set_started()
        self.assertEqual(job_obj.state, "started")

        locks = self.get_locks(job_obj.uuid)

        self.assertEqual(1, len(locks))

    def test_lock(self):
        queue_job = self._get_demo_job("test_started_job")
        job_obj = Job.load(self.env, queue_job.uuid)

        job_obj.set_started()
        job_obj.lock()

        with closing(self.env.registry.cursor()) as new_cr:
            locks = self.get_locks(job_obj.uuid, new_cr)

            # Row should be locked
            self.assertEqual(0, len(locks))

    def test_requeue_dead_jobs(self):
        queue_job = self._get_demo_job("test_enqueued_job")
        job_obj = Job.load(self.env, queue_job.uuid)

        job_obj.set_enqueued()
        job_obj.set_started()
        job_obj.date_enqueued = datetime.now() - timedelta(minutes=1)
        job_obj.store()

        # requeue dead jobs using current cursor
        query = Database(self.env.cr.dbname)._query_requeue_dead_jobs()
        self.env.cr.execute(query)

        uuids_requeued = self.env.cr.fetchall()
        self.assertTrue(queue_job.uuid in j[0] for j in uuids_requeued)

    def test_requeue_orphaned_jobs(self):
        queue_job = self._get_demo_job("test_enqueued_job")
        job_obj = Job.load(self.env, queue_job.uuid)

        # Only enqueued job, don't set it to started to simulate the scenario
        # that system shutdown before job is starting
        job_obj.set_enqueued()
        job_obj.date_enqueued = datetime.now() - timedelta(minutes=1)
        job_obj.store()

        # job is now picked up by the requeue query (which includes orphaned jobs)
        query = Database(self.env.cr.dbname)._query_requeue_dead_jobs()
        self.env.cr.execute(query)
        uuids_requeued = self.env.cr.fetchall()
        self.assertTrue(queue_job.uuid in j[0] for j in uuids_requeued)
