# Copyright 2026 QoQa Services SA (https://www.qoqa.ch)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo.tests.common import HttpCase, tagged
from odoo.tools import mute_logger

from ..job import DONE, ENQUEUED, JobStore


@tagged("-at_install", "post_install")
class TestRunJobController(HttpCase):
    """End-to-end tests of the ``/queue_job/runjob`` route"""

    def _create_enqueued_job(self, **kwargs):
        job = self.env["queue.job"].with_delay()._test_job(**kwargs)
        job.set_enqueued()
        JobStore(self.env).save(job)
        return job

    def _runjob(self, job_uuid):
        response = self.url_open(
            f"/queue_job/runjob?db={self.env.cr.dbname}&job_uuid={job_uuid}"
        )
        response.raise_for_status()
        return response

    def test_runjob(self):
        job = self._create_enqueued_job()
        self._runjob(job.uuid)
        record = job.db_record(self.env)
        # record.invalidate_recordset()
        self.assertEqual(record.state, DONE)

    @mute_logger("odoo.addons.queue_job.executor")
    def test_runjob_unknown_job(self):
        response = self._runjob("not-existing-uuid")
        self.assertEqual(response.text, "")

    @mute_logger("odoo.addons.queue_job.executor")
    def test_runjob_not_enqueued_job_skip(self):
        job = self.env["queue.job"].with_delay()._test_job()
        JobStore(self.env).save(job)  # pending, not enqueued

        self._runjob(job.uuid)

        record = job.db_record(self.env)
        record.invalidate_recordset()
        self.assertNotEqual(record.state, DONE)
        self.assertNotEqual(record.state, ENQUEUED)
