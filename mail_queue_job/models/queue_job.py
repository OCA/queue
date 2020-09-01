# -*- coding: utf-8 -*-
# Copyright 2020 Sunflower IT
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class QueueJob(models.Model):
    _inherit = 'queue.job'

    @api.multi
    @api.returns('self', lambda value: value.id)
    def message_post(self, **kwargs):
        """ Defuse this message if:
            - it has subtype queue_job.mt_job_failed
            - the job was about delivering a mail message
            - that message had subtype queue_job.mt_job_failed
            This is to prevent an endless chain of mails when:
            - a mail fails to be sent
            - the queue job therefore fails
            - it sends mails out to inform queue managers about this
            - these fail
            - the queue job(s) therefore fail
            - etc. """
        relevant_jobs = self
        if kwargs.get('subtype') == 'queue_job.mt_job_failed':
            relevant_jobs = self.filtered(
                lambda j: not j.identity_key.endswith(',X'))
        return super(QueueJob, relevant_jobs).message_post(**kwargs)
