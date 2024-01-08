# Copyright 2019 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import logging

from odoo import api, fields, models

from odoo.addons.queue_job.job import identity_exact

_logger = logging.getLogger(__name__)


class IrCron(models.Model):
    _inherit = "ir.cron"

    no_parallel_queue_job_run = fields.Boolean(
        help="Avoid parallel run. "
        "If the cron job is already running, the new one will be skipped. "
        "By default, odoo never runs the same cron job in parallel. This "
        "option is therefore set to True by default when job is run as a "
        "queue job.",
        default=True,
    )

    run_as_queue_job = fields.Boolean(
        help="Specify if this cron should be ran as a queue job"
    )
    channel_id = fields.Many2one(
        comodel_name="queue.job.channel",
        compute="_compute_run_as_queue_job",
        readonly=False,
        string="Channel",
    )

    @api.depends("run_as_queue_job")
    def _compute_run_as_queue_job(self):
        for cron in self:
            if cron.run_as_queue_job and not cron.channel_id:
                cron.channel_id = self.env.ref("queue_job_cron.channel_root_ir_cron").id
            else:
                cron.channel_id = False

    def _run_job_as_queue_job(self, server_action):
        return server_action.run()

    def method_direct_trigger(self):
        for cron in self:
            if not cron.run_as_queue_job:
                super(IrCron, cron).method_direct_trigger()
            else:
                _cron = cron.with_user(cron.user_id).with_context(
                    lastcall=cron.lastcall
                )
                _cron._delay_run_job_as_queue_job(
                    server_action=_cron.ir_actions_server_id
                )
        return True

    def _callback(self, cron_name, server_action_id, job_id):
        cron = self.env["ir.cron"].sudo().browse(job_id)
        if cron.run_as_queue_job:
            server_action = self.env["ir.actions.server"].browse(server_action_id)
            return cron._delay_run_job_as_queue_job(server_action=server_action)
        else:
            return super()._callback(
                cron_name=cron_name, server_action_id=server_action_id, job_id=job_id
            )

    def _delay_run_job_as_queue_job(self, server_action):
        self.ensure_one()
        identity_key = None
        if self.no_parallel_queue_job_run:
            identity_key = identity_exact
        return self.with_delay(
            priority=self.priority,
            description=self.name,
            channel=self.channel_id.complete_name,
            identity_key=identity_key,
        )._run_job_as_queue_job(server_action=server_action)
