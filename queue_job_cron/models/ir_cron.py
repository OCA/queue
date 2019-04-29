# -*- coding: utf-8 -*-
# Copyright 2017 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import logging
from odoo import api, fields, models, _
from odoo.addons.queue_job.job import job
from odoo.exceptions import ValidationError
from odoo.addons.base.ir.ir_cron import str2tuple

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
    def _run_job_as_queue_job(self, model_name, method_name, args):
        args = str2tuple(args)
        if model_name in self.env:
            model = self.env[model_name]
            if hasattr(model, method_name):
                return getattr(model, method_name)(*args)
            else:
                raise ValidationError(_("Method '%s.%s' does not exist." %
                                        (model_name, method_name)))
        else:
            raise ValidationError(_("Model %r does not exist." % model_name))

    @api.model
    def _callback(self, model_name, method_name, args, job_id):
        cron = self.env['ir.cron'].sudo().browse(job_id)
        if cron.run_as_queue_job:
            return self.with_delay(
                priority=cron.priority,
                description=cron.name,
                channel=cron.channel_id.name)._run_job_as_queue_job(
                    model_name=model_name,
                    method_name=method_name,
                    args=args)
        else:
            return super(IrCron, self)._callback(
                model_name=model_name,
                method_name=method_name,
                args=args,
                job_id=job_id)
