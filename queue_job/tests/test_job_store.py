# Copyright 2026 QoQa Services SA (https://www.qoqa.ch)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo.tests.common import TransactionCase

from ..job import DONE, PENDING, STARTED, JobStore


class TestJobStore(TransactionCase):
    def _new_job(self):
        job = self.env["queue.job"].with_delay()._test_job()
        JobStore(self.env).save(job)
        self.env.flush_all()
        return job

    def test_save_expected_state(self):
        job = self._new_job()  # pending
        job.set_enqueued()
        job.set_started()
        job.set_done()

        saved = JobStore(self.env).save_state(job, expected_states=(PENDING,))
        self.assertTrue(saved)
        record = job.db_record(self.env)
        self.assertEqual(record.state, DONE)

    def test_save_guards_state_unexpected(self):
        job = self._new_job()  # pending
        job.set_enqueued()
        job.set_started()
        job.set_done()

        # when the expected state is started but it is actually done,
        # it should be skipped and reported
        with self.assertLogs("odoo.addons.queue_job.job", "WARNING") as watcher:
            saved = JobStore(self.env).save_state(job, (STARTED,))

        self.assertFalse(saved)

        self.assertIn("not saved", watcher.output[0])

        record = job.db_record(self.env)
        self.assertEqual(record.state, PENDING)

    def test_save_deleted_job(self):
        job = self._new_job()  # pending
        job.db_record(self.env).unlink()
        self.env.flush_all()

        job.set_enqueued()

        with self.assertLogs("odoo.addons.queue_job.job", "WARNING"):
            saved = JobStore(self.env).save_state(job, (PENDING,))
        self.assertFalse(saved)
        self.assertFalse(job.db_record(self.env))
