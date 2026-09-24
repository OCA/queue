# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from datetime import datetime, timedelta

from odoo.tests import tagged

from odoo.addons.queue_job.job import Job
from odoo.addons.queue_job.jobrunner.runner import Database

from .common import JobCommonCase


@tagged("post_install", "-at_install")
class TestRequeueDeadJob(JobCommonCase):
    def test_add_lock_record(self):
        queue_job = self._get_demo_job("test_started_job")
        self.assertEqual(len(queue_job), 1)
        job_obj = Job.load(self.env, queue_job.uuid)

        job_obj.set_started()
        self.assertEqual(job_obj.state, "started")

        self.assertFalse(self.is_job_locked(job_obj))

    def test_lock(self):
        queue_job = self._get_demo_job("test_started_job")
        job_obj = Job.load(self.env, queue_job.uuid)

        job_obj.set_started()
        job_obj.lock("started")

        self.assertTrue(self.is_job_locked(job_obj))

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
