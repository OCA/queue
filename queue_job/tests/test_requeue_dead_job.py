# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from contextlib import closing
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase

from odoo.addons.queue_job.job import Job
from odoo.addons.queue_job.jobrunner.runner import Database


class TestRequeueDeadJob(TransactionCase):
    def create_dummy_job(self, uuid):
        """
        Create dummy job for tests
        """
        return (
            self.env["queue.job"]
            .with_context(
                _job_edit_sentinel=self.env["queue.job"].EDIT_SENTINEL,
            )
            .create(
                {
                    "uuid": uuid,
                    "user_id": self.env.user.id,
                    "state": "pending",
                    "model_name": "queue.job",
                    "method_name": "write",
                }
            )
        )

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
            FOR UPDATE SKIP LOCKED
            """,
            [uuid],
        )

        return cr.fetchall()

    def test_add_lock_record(self):
        queue_job = self.create_dummy_job("test_add_lock")
        job_obj = Job.load(self.env, queue_job.uuid)

        job_obj.set_started()
        self.assertEqual(job_obj.state, "started")

        locks = self.get_locks(job_obj.uuid)

        self.assertEqual(1, len(locks))

    def test_lock(self):
        queue_job = self.create_dummy_job("test_lock")
        job_obj = Job.load(self.env, queue_job.uuid)

        job_obj.set_started()
        job_obj.store()

        locks = self.get_locks(job_obj.uuid)

        self.assertEqual(1, len(locks))

        # commit to update queue_job records in DB
        self.env.cr.commit()  # pylint: disable=E8102

        job_obj.lock()

        with closing(self.env.registry.cursor()) as new_cr:
            locks = self.get_locks(job_obj.uuid, new_cr)

            # Row should be locked
            self.assertEqual(0, len(locks))

        # clean up
        queue_job.unlink()

        self.env.cr.commit()  # pylint: disable=E8102

        # because we committed the cursor, the savepoint of the test method is
        # gone, and this would break TransactionCase cleanups
        self.cr.execute("SAVEPOINT test_%d" % self._savepoint_id)

    def test_requeue_dead_jobs(self):
        uuid = "test_requeue_dead_jobs"

        queue_job = self.create_dummy_job(uuid)
        job_obj = Job.load(self.env, queue_job.uuid)

        job_obj.set_enqueued()
        # simulate enqueuing was in the past
        job_obj.date_enqueued = datetime.now() - timedelta(minutes=1)
        job_obj.set_started()

        job_obj.store()
        self.env.cr.commit()  # pylint: disable=E8102

        # requeue dead jobs using current cursor
        query = Database(self.env.cr.dbname)._query_requeue_dead_jobs()
        self.env.cr.execute(query)

        uuids_requeued = self.env.cr.fetchall()

        self.assertEqual(len(uuids_requeued), 1)
        self.assertEqual(uuids_requeued[0][0], uuid)

        # clean up
        queue_job.unlink()
        self.env.cr.commit()  # pylint: disable=E8102

        # because we committed the cursor, the savepoint of the test method is
        # gone, and this would break TransactionCase cleanups
        self.cr.execute("SAVEPOINT test_%d" % self._savepoint_id)
