# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta
from odoo import api, models, fields


class Attachment(models.Model):
    _inherit = "ir.attachment"

    to_delete = fields.Boolean(string="To delete by CRON", default=False)

    @api.model_cr
    def init(self):
        self._cr.execute(
            "SELECT indexname FROM pg_indexes WHERE "
            "indexname = 'ir_attachment_to_delete_create_date'")
        if not self._cr.fetchone():
            self._cr.execute(
                "CREATE INDEX ir_attachment_to_delete_create_date "
                "ON ir_attachment (to_delete, create_date)")

    @api.model
    def cron_delete(self):
        time_to_live = self.env.\
            ref('base_export_async.attachment_time_to_live').value
        date_today = fields.Date.from_string(fields.Date.today())
        date_to_delete = fields.Date.to_string(
            date_today + relativedelta(days=-int(time_to_live)))
        self.search([('to_delete', '=', True),
                     ('create_date', '<=', date_to_delete)]).unlink()
