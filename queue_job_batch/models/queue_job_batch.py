# Copyright 2019 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api
from odoo.addons.queue_job.job import job


class QueueJobBatch(models.Model):
    _name = 'queue.job.batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Batch of jobs'
    _log_access = False

    name = fields.Char(
        required=True,
        readonly=True,
        track_visibility='onchange',
    )
    job_ids = fields.One2many(
        'queue.job',
        inverse_name='job_batch_id',
        readonly=True,
    )
    job_count = fields.Integer(
        compute='_compute_job_count',
    )
    user_id = fields.Many2one(
        'res.users',
        required=True,
        readonly=True,
        track_visibility='onchange',
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('enqueued', 'Enqueued'),
            ('progress', 'In Progress'),
            ('finished', 'Finished')
        ],
        default='draft',
        required=True,
        readonly=True,
        track_visibility='onchange',
    )
    finished_job_count = fields.Float(
        compute='_compute_job_count',
    )
    failed_job_count = fields.Float(
        compute='_compute_job_count',
    )
    company_id = fields.Many2one(
        'res.company',
        readonly=True,
    )
    is_read = fields.Boolean(
        default=True
    )
    completeness = fields.Float(
        compute='_compute_job_count',
    )
    failed_percentage = fields.Float(
        compute='_compute_job_count',
    )

    def enqueue(self):
        self.filtered(lambda r: r.state == 'draft').write({
            'state': 'enqueued'
        })
        for record in self:
            record.check_state()

    @job
    def check_state(self):
        self.ensure_one()
        if self.state == 'enqueued' and any(
            job.state not in ['pending', 'enqueued'] for job in self.job_ids
        ):
            self.write({'state': 'progress'})
        if self.state != 'progress':
            return True
        if all(job.state == 'done' for job in self.job_ids):
            self.write({
                'state': 'finished',
                'is_read': False,
            })
        return True

    @api.multi
    def set_read(self):
        return self.write({'is_read': True})

    @api.model
    def get_new_batch(self, name, **kwargs):
        vals = kwargs.copy()
        if 'company_id' in self.env.context:
            company_id = self.env.context['company_id']
        else:
            company_model = self.env['res.company']
            company_model = company_model.sudo(self.env.uid)
            company_id = company_model._company_default_get(
                object='queue.job',
                field='company_id'
            ).id
        vals.update({
            'user_id': self.env.uid,
            'name': name,
            'state': 'draft',
            'company_id': company_id,
        })
        return self.sudo().create(vals).sudo(self.env.uid)

    @api.depends('job_ids')
    def _compute_job_count(self):
        for record in self:
            job_count = len(record.job_ids)
            failed_job_count = len(record.job_ids.filtered(
                lambda r: r.state == 'failed'
            ))
            done_job_count = len(record.job_ids.filtered(
                lambda r: r.state == 'done'
            ))
            record.job_count = job_count
            record.finished_job_count = done_job_count
            record.failed_job_count = failed_job_count
            record.completeness = done_job_count / max(1, job_count)
            record.failed_percentage = failed_job_count / max(1, job_count)
