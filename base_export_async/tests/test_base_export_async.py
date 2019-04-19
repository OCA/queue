# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import odoo.tests.common as common
import json

data_csv = {'data': """{"format": "csv", "model": "res.partner",
            "fields": [{"name": "id", "label": "External ID"},
                    {"name": "display_name", "label": "Display Name"},
                    {"name": "email", "label": "Email"},
                    {"name": "phone", "label": "Phone"}],
            "ids": false,
            "domain": [],
            "context": {"lang": "en_US", "tz": "Europe/Brussels", "uid": 2},
            "import_compat": false}"""}

data_xls = {'data': """{"format": "xls", "model": "res.partner",
            "fields": [{"name": "id", "label": "External ID"},
                    {"name": "display_name", "label": "Display Name"},
                    {"name": "email", "label": "Email"},
                    {"name": "phone", "label": "Phone"}],
            "ids": false,
            "domain": [],
            "context": {"lang": "en_US", "tz": "Europe/Brussels", "uid": 2},
            "import_compat": false}"""}


class TestBaseExportAsync(common.TransactionCase):

    def setUp(self):
        super(TestBaseExportAsync, self).setUp()
        self.delay_export_obj = self.env['delay.export']
        self.job_obj = self.env['queue.job']

    def test_delay_export(self):
        """ Check that the call create a new JOB"""
        nbr_job = len(self.job_obj.search([]))
        self.delay_export_obj.delay_export(data_csv)
        new_nbr_job = len(self.job_obj.search([]))
        self.assertEqual(new_nbr_job, nbr_job + 1)

    def test_export_csv(self):
        """ Check that the export generate an attachment and email"""
        params = json.loads(data_csv.get('data'))
        mails = self.env['mail.mail'].search([])
        self.delay_export_obj.export(params)
        new_mail = self.env['mail.mail'].search([]) - mails
        self.assertEqual(len(new_mail), 1)
        self.assertEqual(new_mail.attachment_ids[0].datas_fname,
                         "res.partner.csv")

    def test_export_xls(self):
        """ Check that the export generate an attachment and email"""
        params = json.loads(data_xls.get('data'))
        mails = self.env['mail.mail'].search([])
        self.delay_export_obj.export(params)
        new_mail = self.env['mail.mail'].search([]) - mails
        self.assertEqual(len(new_mail), 1)
        self.assertEqual(new_mail.attachment_ids[0].datas_fname,
                         "res.partner.xls")
