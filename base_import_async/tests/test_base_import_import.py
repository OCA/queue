# Copyright 2024 Camptocamp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import RecordCapturer, TransactionCase

from ..models.base_import_import import OPT_USE_QUEUE


class TestBaseImportImport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.res_partners = cls.env["res.partner"]
        cls.import_wizard = cls.env["base_import.import"]

    def test_normal_import_res_partners(self):
        values = [
            [
                "name",
                "email",
                "is_company",
            ],
            [
                "partner 1",
                "partner1@example.com",
                "1",
            ],
            [
                "partner 2",
                "partner2@example.com",
                "0",
            ],
        ]
        import_vals = {
            "res_model": self.res_partners._name,
            "file": "\n".join([";".join(values) for values in values]),
            "file_type": "text/csv",
        }
        self.import_wizard |= self.import_wizard.create(import_vals)
        opts = {"quoting": '"', "separator": ";", "has_headers": True}
        preview = self.import_wizard.parse_preview(opts)
        self.assertEqual(
            preview["matches"],
            {
                0: ["name"],
                1: ["email"],
                2: ["is_company"],
            },
        )
        with RecordCapturer(self.res_partners, []) as capture:
            results = self.import_wizard.execute_import(
                [fnames[0] for fnames in preview["matches"].values()],
                [],
                opts,
            )
        # if result is empty, no import error
        self.assertItemsEqual(results["messages"], [])
        records_created = capture.records
        self.assertEqual(len(records_created), 2)
        self.assertIn("partner1", records_created[0].email)

    def test_wrong_import_res_partners(self):
        values = [
            [
                "name",
                "email",
                "date",  # Adding date field to trigger parsing error
            ],
            [
                "partner 1",
                "partner1@example.com",
                "21-13-2024",
            ],
            [
                "partner 2",
                "partner2@example.com",
                "2024-13-45",
            ],
        ]
        opts = {
            "quoting": '"',
            "separator": ";",
            "has_headers": True,
            "date_format": "%Y-%m-%d",  # Set specific date format
            OPT_USE_QUEUE: True,
        }
        import_vals = {
            "res_model": self.res_partners._name,
            "file": "\n".join([";".join(row) for row in values]),
            "file_type": "text/csv",
        }
        import_wizard = self.import_wizard.create(import_vals)
        preview = import_wizard.parse_preview(opts)
        results = import_wizard.execute_import(
            [field[0] for field in preview["matches"].values()],
            ["name", "email", "date"],  # Include date in fields to import
            opts,
        )
        self.assertTrue(any(msg["type"] == "error" for msg in results["messages"]))
