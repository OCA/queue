# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import csv
import io
import json
import zipfile
from unittest import mock
from unittest.mock import patch
from xml.etree import ElementTree

import freezegun
from dateutil.relativedelta import relativedelta

import odoo.tests.common as common
from odoo import fields, models

from odoo.addons.web.controllers import export

data_csv = {
    "data": """{"format": "csv", "model": "res.partner",
            "fields": [{"name": "id", "label": "External ID"},
                    {"name": "display_name", "label": "Display Name"},
                    {"name": "email", "label": "Email"},
                    {"name": "phone", "label": "Phone"}],
            "ids": false,
            "domain": [],
            "context": {"lang": "en_US", "tz": "Europe/Brussels", "uid": 2},
            "import_compat": false,
            "user_ids": [6]
            }"""
}

data_xls = {
    "data": """{"format": "xls", "model": "res.partner",
            "fields": [{"name": "id", "label": "External ID"},
                    {"name": "display_name", "label": "Display Name"},
                    {"name": "email", "label": "Email"},
                    {"name": "phone", "label": "Phone"}],
            "ids": false,
            "domain": [],
            "context": {"lang": "en_US", "tz": "Europe/Brussels", "uid": 2},
            "import_compat": false,
            "user_ids": [6]
            }"""
}


class TestBaseExportAsync(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.delay_export_obj = self.env["delay.export"]
        self.job_obj = self.env["queue.job"]
        with patch("odoo.http._request_stack") as mock_request_stack:
            mock_request = mock.Mock(env=self.env)
            mock_request_stack.push(mock_request)
            self.addCleanup(mock_request_stack.pop)

    def test_delay_export(self):
        """Check that the call create a new JOB"""
        nbr_job = len(self.job_obj.search([]))
        self.delay_export_obj.delay_export(data_csv)
        new_nbr_job = len(self.job_obj.search([]))
        self.assertEqual(new_nbr_job, nbr_job + 1)

    def test_export_csv(self):
        """Check that the export generate an attachment and email"""
        params = json.loads(data_csv.get("data"))
        mails = self.env["mail.mail"].search([])
        attachments = self.env["ir.attachment"].search([])
        self.delay_export_obj.export(params)
        new_mail = self.env["mail.mail"].search([]) - mails
        new_attachment = self.env["ir.attachment"].search([]) - attachments
        self.assertEqual(len(new_mail), 1)
        self.assertEqual(new_attachment.name, "res.partner.csv")

    def test_export_xls(self):
        """Check that the export generate an attachment and email"""
        params = json.loads(data_xls.get("data"))
        mails = self.env["mail.mail"].search([])
        attachments = self.env["ir.attachment"].search([])
        with patch.object(export, "request", mock.Mock(env=self.env)):
            self.delay_export_obj.export(params)
        new_mail = self.env["mail.mail"].search([]) - mails
        new_attachment = self.env["ir.attachment"].search([]) - attachments
        self.assertEqual(len(new_mail), 1)
        self.assertEqual(new_attachment.name, "res.partner.xls")

    def test_export_csv_batches(self):
        """Ensure all records are exported when split in batches"""
        partners = self.env["res.partner"].create(
            [{"name": f"Async Export {i}"} for i in range(5)]
        )
        params = json.loads(data_csv.get("data"))
        params["ids"] = partners.ids
        params["fields"] = [{"name": "name", "label": "Name"}]
        partner_class = type(self.env["res.partner"])

        with (
            patch.object(models, "PREFETCH_MAX", 2),
            patch.object(
                partner_class,
                "export_data",
                autospec=True,
                side_effect=partner_class.export_data,
            ) as export_data,
        ):
            content = self.delay_export_obj._get_file_content(params)
            rows = list(csv.reader(io.StringIO(content.decode("utf-8"))))
            batch_sizes = [len(call.args[0]) for call in export_data.call_args_list]

        self.assertEqual(batch_sizes, [2, 2, 1])
        self.assertEqual(
            rows, [["Name"]] + [[name] for name in partners.mapped("name")]
        )

    def test_export_xlsx_content(self):
        """Ensure xlsx's content is exported by batches using constant
        memory"""
        partners = self.env["res.partner"].create(
            [{"name": f"Async Export {i}"} for i in range(5)]
        )
        params = json.loads(data_xls.get("data"))
        params["ids"] = partners.ids
        params["fields"] = [{"name": "name", "label": "Name"}]

        with (
            patch.object(models, "PREFETCH_MAX", 2),
            patch.object(export, "request", mock.Mock(env=self.env)),
        ):
            content = self.delay_export_obj._get_file_content(params)

        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        # In constant memory mode, the strings are written in the worksheet
        # instead of the shared strings table
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        rows = [
            [cell.findtext("x:is/x:t", namespaces=ns) for cell in row]
            for row in sheet.iterfind("x:sheetData/x:row", ns)
        ]

        self.assertEqual(
            rows, [["Name"]] + [[name] for name in partners.mapped("name")]
        )

    def test_cron_delete(self):
        """Check that cron delete attachment after TTL"""
        params = json.loads(data_csv.get("data"))
        attachments = self.env["ir.attachment"].search([])
        self.delay_export_obj.export(params)
        new_attachment = self.env["ir.attachment"].search([]) - attachments
        time_to_live = (
            self.env["ir.config_parameter"].sudo().get_param("attachment.ttl", 7)
        )
        date_today = fields.Datetime.now()
        date_past_ttl = date_today + relativedelta(days=int(time_to_live))
        with freezegun.freeze_time(date_past_ttl):
            self.delay_export_obj.cron_delete()

        # The attachment must be deleted
        self.assertFalse(new_attachment.exists())
