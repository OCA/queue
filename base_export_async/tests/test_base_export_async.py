# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
from unittest.mock import patch

import freezegun
from dateutil.relativedelta import relativedelta

import odoo.tests.common as common
from odoo import fields

# This is the key import for fixing "object unbound"
from odoo.addons.website.tools import MockRequest

# Data definitions
data_csv = {
    "data": json.dumps(
        {
            "format": "csv",
            "model": "res.partner",
            "fields": [
                {"name": "id", "label": "External ID"},
                {"name": "display_name", "label": "Display Name"},
                {"name": "email", "label": "Email"},
                {"name": "phone", "label": "Phone"},
            ],
            "ids": False,
            "domain": [],
            "context": {"lang": "en_US", "tz": "Europe/Brussels", "uid": 2},
            "import_compat": False,
            "user_ids": [2],
        }
    )
}

data_xls = {
    "data": json.dumps(
        {
            "format": "xls",
            "model": "res.partner",
            "fields": [
                {"name": "id", "label": "External ID"},
                {"name": "display_name", "label": "Display Name"},
                {"name": "email", "label": "Email"},
                {"name": "phone", "label": "Phone"},
            ],
            "ids": False,
            "domain": [],
            "context": {"lang": "en_US", "tz": "Europe/Brussels", "uid": 2},
            "import_compat": False,
            "user_ids": [2],
        }
    )
}


class TestBaseExportAsync(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.delay_export_obj = self.env["delay.export"]
        self.job_obj = self.env["queue.job"]

        # We use MockRequest as a context manager to bind the request object correctly
        self.mock_request_stack = MockRequest(self.env)
        self.mock_request_stack.__enter__()
        self.addCleanup(self.mock_request_stack.__exit__, None, None, None)

    def test_delay_export(self):
        """Check that the call creates a new JOB"""
        nbr_job = self.job_obj.search_count([])
        self.delay_export_obj.delay_export(data_csv)
        new_nbr_job = self.job_obj.search_count([])
        self.assertEqual(new_nbr_job, nbr_job + 1)

    def test_export_csv(self):
        """Check that the export generates an attachment and email"""
        params = json.loads(data_csv.get("data"))
        mails = self.env["mail.mail"].search([])
        attachments = self.env["ir.attachment"].search([])

        self.delay_export_obj.export(params)

        new_mail = self.env["mail.mail"].search([]) - mails
        new_attachment = self.env["ir.attachment"].search([]) - attachments

        self.assertEqual(len(new_mail), 1)
        self.assertEqual(new_attachment.name, "res.partner.csv")

    def test_export_xls(self):
        """Check that the export generates an attachment and email"""
        params = json.loads(data_xls.get("data"))
        mails = self.env["mail.mail"].search([])
        attachments = self.env["ir.attachment"].search([])

        # Patch the class method directly
        with patch(
            "odoo.addons.web.controllers.export.ExcelExport.from_data",
            return_value=b"\x41\x42\x43\x44",
        ):
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
        date_past_ttl = date_today + relativedelta(days=int(time_to_live) + 1)

        with freezegun.freeze_time(date_past_ttl):
            self.delay_export_obj.cron_delete()

        self.assertFalse(new_attachment.exists())
