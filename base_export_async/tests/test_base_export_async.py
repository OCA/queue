# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

import odoo.tests.common as common
from dateutil.relativedelta import relativedelta
from odoo import fields

data_csv = {
    "data": """{"format": "csv", "model": "res.partner",
            "fields": [{"name": "id", "label": "External ID"},
                    {"name": "display_name", "label": "Display Name"},
                    {"name": "email", "label": "Email"},
                    {"name": "phone", "label": "Phone"}],
            "ids": false,
            "domain": [],
            "context": {"lang": "en_US", "tz": "Europe/Brussels", "uid": 2},
            "import_compat": false}"""
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
            "import_compat": false}"""
}


class TestBaseExportAsync(common.TransactionCase):
    def setUp(self):
        super(TestBaseExportAsync, self).setUp()
        self.delay_export_obj = self.env["delay.export"]
        self.job_obj = self.env["queue.job"]

    def test_delay_export(self):
        """ Check that the call create a new JOB"""
        nbr_job = len(self.job_obj.search([]))
        self.delay_export_obj.delay_export(data_csv)
        new_nbr_job = len(self.job_obj.search([]))
        self.assertEqual(new_nbr_job, nbr_job + 1)

    def test_export_csv(self):
        """ Check that the export generate an attachment and email"""
        params = json.loads(data_csv.get("data"))
        mails = self.env["mail.mail"].search([])
        attachments = self.env["ir.attachment"].search([])
        self.delay_export_obj.export(params)
        new_mail = self.env["mail.mail"].search([]) - mails
        new_attachment = self.env["ir.attachment"].search([]) - attachments
        self.assertEqual(len(new_mail), 1)
        self.assertEqual(new_attachment.datas_fname, "res.partner.csv")

    def test_export_xls(self):
        """ Check that the export generate an attachment and email"""
        params = json.loads(data_xls.get("data"))
        mails = self.env["mail.mail"].search([])
        attachments = self.env["ir.attachment"].search([])
        self.delay_export_obj.export(params)
        new_mail = self.env["mail.mail"].search([]) - mails
        new_attachment = self.env["ir.attachment"].search([]) - attachments
        self.assertEqual(len(new_mail), 1)
        self.assertEqual(new_attachment.datas_fname, "res.partner.xls")

    def test_cron_delete(self):
        """ Check that cron delete attachment after TTL"""
        params = json.loads(data_csv.get("data"))
        attachments = self.env["ir.attachment"].search([])
        self.delay_export_obj.export(params)
        new_attachment = self.env["ir.attachment"].search([]) - attachments
        time_to_live = (
            self.env["ir.config_parameter"].sudo().get_param("attachment.ttl", 7)
        )
        date_today = fields.Date.today()
        date_to_delete = date_today + relativedelta(days=-int(time_to_live))
        # Update create_date with today - TTL
        self.delay_export_obj.search([]).write({"create_date": date_to_delete})
        self.delay_export_obj.sudo().cron_delete()
        # The attachment must be deleted
        self.assertFalse(new_attachment.exists())
