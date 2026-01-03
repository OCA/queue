# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from unittest import mock

from odoo.tests import tagged

from odoo.addons.queue_job.controllers.main import RunJobController
from odoo.addons.queue_job.job import ENQUEUED, STARTED

from .common import JobCommonCase


@tagged("post_install", "-at_install")
class TestRequeueDeadJob(JobCommonCase):
    def test_acquire_enqueued_job(self):
        job_record = self._get_demo_job(uuid="test_enqueued_job")
        self.assertFalse(
            self.env["queue.job.lock"].search(
                [("queue_job_id", "=", job_record.id)],
            ),
            "A job lock record should not exist at this point",
        )
        with mock.patch.object(
            self.env.cr, "commit", mock.Mock(side_effect=self.env.flush_all)
        ) as mock_commit:
            job = RunJobController._acquire_job(self.env, job_uuid="test_enqueued_job")
            mock_commit.assert_called_once()
            self.assertIsNotNone(job)
            self.assertEqual(job.uuid, "test_enqueued_job")
            self.assertEqual(job.state, STARTED)
            self.assertTrue(
                self.env["queue.job.lock"].search(
                    [("queue_job_id", "=", job_record.id)]
                ),
                "A job lock record should exist at this point",
            )

    def test_acquire_any_enqueued_job(self):
        available_job_uuids = (
            self.env["queue.job"].search([("state", "=", ENQUEUED)]).mapped("uuid")
        )
        with mock.patch.object(
            self.env.cr, "commit", mock.Mock(side_effect=self.env.flush_all)
        ) as mock_commit:
            job = RunJobController._acquire_job(self.env)
            mock_commit.assert_called_once()
            self.assertIsNotNone(job)
            self.assertIn(job.uuid, available_job_uuids)
            self.assertEqual(job.state, STARTED)
            self.assertTrue(
                self.env["queue.job.lock"].search(
                    [("queue_job_id", "=", job.db_record().id)]
                ),
                "A job lock record should exist at this point",
            )

    def test_acquire_started_job(self):
        with mock.patch.object(
            self.env.cr, "commit", mock.Mock(side_effect=self.env.flush_all)
        ) as mock_commit:
            job = RunJobController._acquire_job(self.env, "test_started_job")
            mock_commit.assert_not_called()
            self.assertIsNone(job)
