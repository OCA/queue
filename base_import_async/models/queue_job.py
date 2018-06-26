# Copyright 2017 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models, _


class QueueJob(models.Model):
    """ Job status and result """
    _inherit = 'queue.job'

    @api.multi
    def _related_action_attachment(self):
        res_id = self.kwargs.get('att_id')
        action = {
            'name': _("Attachment"),
            'type': 'ir.actions.act_window',
            'res_model': "ir.attachment",
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': res_id,
        }
        return action
