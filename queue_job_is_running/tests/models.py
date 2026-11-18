# Copyright 2026 Ecosoft Co., Ltd. (https://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class QueueRunningTestModel(models.Model):
    _name = "queue.running.test.model"
    _description = "Queue Running Test Model"
    _inherit = ["queue.job.status.mixin"]

    name = fields.Char()

    def action_process(self):
        for record in self:
            record.with_delay()._process_in_background()

    def _process_in_background(self):
        # Do something.
        return True
