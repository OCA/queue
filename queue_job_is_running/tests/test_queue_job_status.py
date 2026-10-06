# Copyright 2026 Ecosoft Co., Ltd. (https://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from lxml import etree
from odoo_test_helper import FakeModelLoader

from odoo.tests import common
from odoo.tools import SQL, index_exists

from odoo.addons.queue_job.job import (
    CANCELLED,
    DONE,
    ENQUEUED,
    FAILED,
    PENDING,
    STARTED,
    WAIT_DEPENDENCIES,
)
from odoo.addons.queue_job.tests.common import JobMixin
from odoo.addons.queue_job_is_running.models.constants import (
    RUNNING_RECORD_IDS_INDEX,
)

RUNNING_STATES = (WAIT_DEPENDENCIES, PENDING, ENQUEUED, STARTED)
TERMINAL_STATES = (DONE, FAILED, CANCELLED)


class TestQueueJobStatus(common.TransactionCase, JobMixin):
    def setUp(self):
        super().setUp()
        # Register the test-only model on the fly so it (and its table) exist
        # only for this test run and never ship in production.
        self.loader = FakeModelLoader(self.env, self.__module__)
        self.loader.backup_registry()
        from .models import QueueRunningTestModel

        self.loader.update_registry((QueueRunningTestModel,))
        self.record = self.env["queue.running.test.model"].create({"name": "demo"})

    def tearDown(self):
        self.loader.restore_registry()
        super().tearDown()

    def _jobs(self, record):
        """Return queue jobs for the model under test."""
        return self.env["queue.job"].search([("model_name", "=", record._name)])

    def _refresh(self, record):
        """Drop the cached computed value so it is recomputed on next read.

        On the client side the form is reloaded after an action, which gives
        a fresh value; in tests we must drop the in-memory cache of the
        non-stored computed field, otherwise the previous value sticks.
        """
        record.invalidate_recordset(["running_job_names"])
        return record

    def test_default_and_new_record(self):
        self.assertFalse(self._refresh(self.record).running_job_names)
        new_record = self.env["queue.running.test.model"].new({"name": "new"})
        with self.assertQueryCount(0):
            self.assertFalse(new_record.running_job_names)

    def test_job_states(self):
        self.record.action_process()
        job = self._jobs(self.record)
        self.assertEqual(len(job), 1)

        for state in RUNNING_STATES:
            with self.subTest(state=state):
                job.state = state
                self.assertEqual(
                    self._refresh(self.record).running_job_names,
                    job.name,
                )

        for state in TERMINAL_STATES:
            with self.subTest(state=state):
                job.state = state
                self.assertFalse(self._refresh(self.record).running_job_names)

    def test_unrelated_record_not_flagged(self):
        other = self.env["queue.running.test.model"].create({"name": "other"})
        self.record.action_process()
        job = self._jobs(self.record)
        self.assertEqual(self._refresh(self.record).running_job_names, job.name)
        self.assertFalse(self._refresh(other).running_job_names)

    def test_multi_record_job(self):
        other = self.env["queue.running.test.model"].create({"name": "other"})
        records = self.record | other
        records.with_delay()._process_in_background()
        job = self._jobs(self.record)
        self.assertEqual(set(job.records.ids), set(records.ids))
        self.assertEqual(
            self._refresh(records).mapped("running_job_names"),
            [job.name, job.name],
        )

    def test_multiple_job_names(self):
        self.record.with_delay(description="Second job")._process_in_background()
        self.record.with_delay(description="First job")._process_in_background()
        self.assertEqual(
            self._refresh(self.record).running_job_names,
            "First job, Second job",
        )

    def test_migrated_json_object_storage(self):
        self.record.action_process()
        job = self._jobs(self.record)
        job.flush_recordset(["records"])
        self.env.cr.execute(
            SQL(
                """
                UPDATE queue_job
                   SET records = (records #>> '{}')::jsonb
                 WHERE id = %s
                """,
                job.id,
            )
        )
        job.invalidate_recordset(["records"])
        self.assertEqual(self._refresh(self.record).running_job_names, job.name)

    def test_compute_uses_one_query(self):
        self.record.action_process()
        self._refresh(self.record)
        with self.assertQueryCount(1):
            running_job_names = self.record.running_job_names
        self.assertTrue(running_job_names)

    def test_running_record_ids_index_exists(self):
        self.assertTrue(index_exists(self.env.cr, RUNNING_RECORD_IDS_INDEX))

    def test_form_view_has_running_job_alert(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "queue.running.test.model.form",
                "model": self.record._name,
                "arch": """
                    <form>
                        <sheet>
                            <group><field name="name" /></group>
                        </sheet>
                    </form>
                """,
            }
        )
        result = self.record.get_view(view_id=view.id, view_type="form")
        arch = etree.fromstring(result["arch"])
        alerts = arch.xpath(
            "/form/div[contains(concat(' ', normalize-space(@class), ' '), "
            "' alert ')]"
        )
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].get("invisible"), "not running_job_names")
        self.assertIn("running_job_names", result["models"][self.record._name])
        self.assertEqual(
            alerts[0].xpath(".//field")[0].get("name"),
            "running_job_names",
        )
