# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
from unittest import mock
from unittest.mock import patch

import freezegun
from dateutil.relativedelta import relativedelta

import odoo.tests.common as common
from odoo import fields

from odoo.addons.web.controllers.export import ExcelExport

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
            "user_ids": [2]
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
            "user_ids": [2]
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
        with patch.object(ExcelExport, "from_data", return_value=b"\x41\x42\x43\x44"):
            self.delay_export_obj.export(params)
        new_mail = self.env["mail.mail"].search([]) - mails
        new_attachment = self.env["ir.attachment"].search([]) - attachments
        self.assertEqual(len(new_mail), 1)
        self.assertEqual(new_attachment.name, "res.partner.xls")

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
