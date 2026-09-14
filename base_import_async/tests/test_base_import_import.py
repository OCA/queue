# Copyright 2024 Camptocamp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import RecordCapturer, TransactionCase

from odoo.addons.queue_job.exception import FailedJobError

from ..wizard.base_import_import import (
    INIT_PRIORITY,
    OPT_CHUNK_SIZE,
    OPT_HAS_HEADER,
    OPT_QUOTING,
    OPT_SEPARATOR,
    OPT_USE_QUEUE,
)


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

    def test_execute_import_res_partners_async(self):
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
            "file_name": "partners.csv",
        }
        import_wizard = self.import_wizard.create(import_vals)
        opts = {
            OPT_QUOTING: '"',
            OPT_SEPARATOR: ";",
            OPT_HAS_HEADER: True,
            OPT_USE_QUEUE: True,
        }
        preview = import_wizard.parse_preview(opts)
        with RecordCapturer(self.env["queue.job"], []) as capture:
            result = import_wizard.execute_import(
                [field[0] for field in preview["matches"].values()],
                [],
                opts,
            )
        self.assertEqual(result, [])
        self.assertEqual(len(capture.records), 1)
        job = capture.records[0]
        self.assertEqual(job.method_name, "_split_file")
        self.assertEqual(job.model_name, "base_import.import")
        attachment = self.env["ir.attachment"].search(
            [("res_model", "=", "queue.job"), ("res_id", "=", job.id)], limit=1
        )
        self.assertTrue(attachment)

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

    def test_split_file_creates_chunk_jobs_and_links_attachments(self):
        import_wizard = self.import_wizard.create(
            {
                "res_model": self.res_partners._name,
                "file": "dummy",
                "file_type": "text/csv",
            }
        )
        fields = ["name", "email", "is_company"]
        data = [
            ["partner 1", "partner1@example.com", "1"],
            ["partner 2", "partner2@example.com", "0"],
            ["partner 3", "partner3@example.com", "0"],
        ]
        opts = {
            OPT_QUOTING: '"',
            OPT_SEPARATOR: ";",
            OPT_HAS_HEADER: True,
            OPT_CHUNK_SIZE: 2,
        }
        attachment = import_wizard._create_csv_attachment(
            fields, data, opts, "partners.csv"
        )
        with RecordCapturer(self.env["queue.job"], []) as capture:
            import_wizard._split_file(
                model_name=self.res_partners._name,
                translated_model_name="Contacts",
                attachment=attachment,
                options=opts,
                file_name="partners.csv",
            )
        jobs = capture.records.sorted("priority")
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs.mapped("method_name"), ["_import_one_chunk"] * 2)
        self.assertEqual(jobs.mapped("priority"), [INIT_PRIORITY, INIT_PRIORITY + 1])
        self.assertEqual(
            jobs.mapped("name"),
            [
                "Import Contacts from file partners.csv - #0 - lines 2 to 3",
                "Import Contacts from file partners.csv - #1 - lines 4 to 4",
            ],
        )
        chunk_attachments = self.env["ir.attachment"].search(
            [("name", "in", ["partners-0.csv", "partners-1.csv"])]
        )
        self.assertEqual(len(chunk_attachments), 2)
        self.assertTrue(all(att.res_model == "queue.job" for att in chunk_attachments))
        self.assertTrue(all(att.res_id in jobs.ids for att in chunk_attachments))

    def test_import_one_chunk_success_and_error(self):
        import_wizard = self.import_wizard.create(
            {
                "res_model": self.res_partners._name,
                "file": "dummy",
                "file_type": "text/csv",
            }
        )
        opts = {OPT_QUOTING: '"', OPT_SEPARATOR: ";"}

        fields = ["name", "email", "is_company"]
        data = [
            ["partner 1", "partner1@example.com", "1"],
            ["partner 2", "partner2@example.com", "0"],
        ]
        attachment = import_wizard._create_csv_attachment(
            fields, data, opts, "partners.csv"
        )
        with RecordCapturer(self.res_partners, []) as capture:
            result = import_wizard._import_one_chunk(
                self.res_partners._name, attachment, opts
            )
        self.assertEqual(result["messages"], [])
        self.assertEqual(len(capture.records), 2)

        invalid_fields = ["name", "company_type"]
        invalid_data = [["partner 3", "invalid"]]
        invalid_attachment = import_wizard._create_csv_attachment(
            invalid_fields, invalid_data, opts, "invalid.csv"
        )
        with self.assertRaises(FailedJobError):
            import_wizard._import_one_chunk(
                self.res_partners._name, invalid_attachment, opts
            )
