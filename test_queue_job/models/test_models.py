# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.queue_job.exception import RetryableJobError
from odoo import api, fields, models
from odoo.addons.queue_job.job import job


class TestQueueJob(models.Model):

    _name = 'test.queue.job'
    _description = "Test model for queue.job"

    name = fields.Char()

    @job
    @api.multi
    def normal_job(self, *args, **kwargs):
        """ Method used for tests

        Return always the arguments and keyword arguments received
        """
        return
        if kwargs.get('raise_retry'):
            raise RetryableJobError('Must be retried later')
        if kwargs.get('return_context'):
            return self.env.context
        return args, kwargs

    @job
    def no_description(self):
        return

    @job(retry_pattern={1:  60, 2: 180, 3:  10, 5: 300})
    def job_with_retry_pattern(self):
        return

    @job(retry_pattern={3:  180})
    def job_with_retry_pattern__no_zero(self):
        return

    @job
    def mapped(self, func):
        return super(TestQueueJob, self).mapped(func)

    @api.multi
    def testing_related_method(self, **kwargs):
        if 'url' in kwargs:
            subject = self.args[0]
            return {
                'type': 'ir.actions.act_url',
                'target': 'new',
                'url': kwargs['url'].format(subject=subject),
            }
        return self, kwargs


class TestQueueChannel(models.Model):

    _name = 'test.queue.channel'
    _description = "Test model for queue.channel"

    @job
    def job_a(self):
        return

    @job
    def job_b(self):
        return

    @job(default_channel='root.sub.subsub')
    def job_sub_channel(self):
        return
