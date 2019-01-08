# Copyright 2019 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import logging
from odoo import api, fields, models
from odoo.addons.queue_job.job import job

_logger = logging.getLogger(__name__)


class IrCron(models.Model):
    _inherit = 'ir.cron'

    run_as_queue_job = fields.Boolean(help="Specify if this cron should be "
                                           "ran as a queue job")
    channel_id = fields.Many2one(comodel_name='queue.job.channel',
                                 string='Channel')

    @api.onchange('run_as_queue_job')
    def onchange_run_as_queue_job(self):
        for cron in self:
            if cron.run_as_queue_job and not cron.channel_id:
                cron.channel_id = self.env.ref(
                    'queue_job_cron.channel_root_ir_cron').id

    @job(default_channel='root.ir_cron')
    @api.model
    def _run_job_as_queue_job(self, server_action):
        return server_action.run()

    @api.multi
    def method_direct_trigger(self):
        if self.run_as_queue_job:
            return self.with_delay(
                priority=self.priority,
                description=self.name,
                channel=self.channel_id.name)._run_job_as_queue_job(
                server_action=self.ir_actions_server_id)
        else:
            return super(IrCron, self).method_direct_trigger()

    @api.model
    def _callback(self, cron_name, server_action_id, job_id):
        cron = self.env['ir.cron'].sudo().browse(job_id)
        if cron.run_as_queue_job:
            server_action = self.env['ir.actions.server'].browse(
                server_action_id)
            return self.with_delay(
                priority=cron.priority,
                description=cron.name,
                channel=cron.channel_id.name)._run_job_as_queue_job(
                    server_action=server_action)
        else:
            return super(IrCron, self)._callback(
                cron_name=cron_name,
                server_action_id=server_action_id,
                job_id=job_id)
