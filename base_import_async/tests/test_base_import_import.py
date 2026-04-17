# Copyright 2024 Camptocamp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64
import datetime
import uuid
from unittest import mock

from odoo.tests.common import RecordCapturer, TransactionCase

from odoo.addons.queue_job.tests.common import trap_jobs

from ..wizards.base_import_import import OPT_USE_QUEUE


class TestBaseImportImport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.res_partners = cls.env["res.partner"]
        cls.base_import = cls.env["base_import.import"]
        cls.queue_job = cls.env["queue.job"]

    def _create_import_wizard(self, rows, file_name="partners.csv"):
        csv_content = "\n".join(";".join(row) for row in rows)
        return self.base_import.create(
            {
                "res_model": self.res_partners._name,
                "file": csv_content.encode(),
                "file_name": file_name,
                "file_type": "text/csv",
            }
        )

    def _get_import_preview(self, import_wizard, options):
        preview = import_wizard.parse_preview(options)
        self.assertIsNone(preview.get("error"), preview.get("error"))
        return preview

    def _get_import_fields(self, import_wizard, options):
        preview = self._get_import_preview(import_wizard, options)
        return ["/".join(field_names) for field_names in preview["matches"].values()], (
            preview["headers"] or []
        )

    def test_normal_import_res_partners(self):
        import_wizard = self._create_import_wizard(
            [
                ["name", "email", "is_company"],
                ["partner 1", "partner1@example.com", "1"],
                ["partner 2", "partner2@example.com", "0"],
            ]
        )
        options = {"quoting": '"', "separator": ";", "has_headers": True}
        import_fields, columns = self._get_import_fields(import_wizard, options)

        with RecordCapturer(self.res_partners, []) as capture:
            result = import_wizard.execute_import(import_fields, columns, options)

        self.assertCountEqual(result["messages"], [])
        self.assertEqual(len(capture.records), 2)
        self.assertCountEqual(
            capture.records.mapped("email"),
            [
                "partner1@example.com",
                "partner2@example.com",
            ],
        )

    def test_async_import_schedules_and_imports_records(self):
        import_wizard = self._create_import_wizard(
            [
                ["name", "email", "is_company"],
                ["async partner 1", "async1@example.com", "1"],
                ["async partner 2", "async2@example.com", "0"],
            ]
        )
        options = {
            "quoting": '"',
            "separator": ";",
            "has_headers": True,
            OPT_USE_QUEUE: True,
        }
        import_fields, columns = self._get_import_fields(import_wizard, options)

        with trap_jobs() as trap:
            result = import_wizard.execute_import(import_fields, columns, options)
            self.assertEqual(result, [])
            trap.assert_jobs_count(1, only=import_wizard._split_file)

            with RecordCapturer(self.res_partners, []) as capture:
                trap.perform_enqueued_jobs()
                trap.assert_jobs_count(1, only=import_wizard._import_one_chunk)
                trap.perform_enqueued_jobs()

        self.assertEqual(len(capture.records), 2)
        self.assertCountEqual(
            capture.records.mapped("name"),
            [
                "async partner 1",
                "async partner 2",
            ],
        )

    def test_async_import_uses_datetime_prevalidation(self):
        import_wizard = self.base_import.create({"res_model": self.res_partners._name})

        with trap_jobs() as trap:
            with mock.patch.object(
                type(import_wizard),
                "_convert_import_data",
                return_value=(
                    [
                        [datetime.date(2026, 4, 17)],
                    ],
                    ["name"],
                ),
            ):
                result = import_wizard.execute_import(
                    ["name"],
                    ["name"],
                    {OPT_USE_QUEUE: True},
                )

        self.assertEqual(trap.jobs_count(), 0)
        self.assertEqual(len(result["messages"]), 1)
        self.assertIn(
            "does not accept date/time values", result["messages"][0]["message"]
        )

    def test_async_import_applies_fallback_values(self):
        import_wizard = self._create_import_wizard(
            [
                ["name", "company_type"],
                ["fallback partner", "Unknown value"],
            ],
            file_name="fallback.csv",
        )
        options = {
            "quoting": '"',
            "separator": ";",
            "has_headers": True,
            OPT_USE_QUEUE: True,
            "fallback_values": {
                "company_type": {
                    "fallback_value": "person",
                    "field_model": "res.partner",
                    "field_type": "selection",
                }
            },
        }
        import_fields, columns = self._get_import_fields(import_wizard, options)

        with trap_jobs() as trap:
            result = import_wizard.execute_import(import_fields, columns, options)
            self.assertEqual(result, [])
            trap.perform_enqueued_jobs()
            trap.perform_enqueued_jobs()

        partner = self.res_partners.search([("name", "=", "fallback partner")], limit=1)
        self.assertTrue(partner)
        self.assertEqual(partner.company_type, "person")

    def test_related_action_attachment_returns_linked_attachment(self):
        queue_job = self.queue_job.with_context(
            _job_edit_sentinel=self.queue_job.EDIT_SENTINEL
        ).create(
            {
                "uuid": str(uuid.uuid4()),
                "state": "done",
                "user_id": self.env.user.id,
                "company_id": self.env.company.id,
                "kwargs": {},
            }
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": "chunk.csv",
                "datas": base64.b64encode(b"name\nlinked attachment"),
                "res_model": "queue.job",
                "res_id": queue_job.id,
            }
        )

        action = queue_job._related_action_attachment()

        self.assertEqual(action["res_model"], "ir.attachment")
        self.assertEqual(action["res_id"], attachment.id)
