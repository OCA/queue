# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models
from odoo.addons.queue_job.job import job, related_action
from odoo.addons.queue_job.exception import RetryableJobError


class QueueJob(models.Model):

    _inherit = 'queue.job'

    @api.multi
    def testing_related_method(self, **kwargs):
        return self, kwargs

    @api.multi
    def testing_related__none(self, **kwargs):
        return None

    @api.multi
    def testing_related__url(self, **kwargs):
        assert 'url' in kwargs, "url required"
        subject = self.args[0]
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': kwargs['url'].format(subject=subject),
        }


class TestQueueJob(models.Model):

    _name = 'test.queue.job'
    _description = "Test model for queue.job"

    name = fields.Char()

    @job
    @related_action(action='testing_related_method')
    @api.multi
    def testing_method(self, *args, **kwargs):
        """ Method used for tests

        Return always the arguments and keyword arguments received
        """
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

    @job
    def job_alter_mutable(self, mutable_arg, mutable_kwarg=None):
        mutable_arg.append(2)
        mutable_kwarg['b'] = 2
        return mutable_arg, mutable_kwarg


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


class TestRelatedAction(models.Model):

    _name = 'test.related.action'
    _description = "Test model for related actions"

    @job
    def testing_related_action__no(self):
        return

    @job
    @related_action()  # default action returns None
    def testing_related_action__return_none(self):
        return

    @job
    @related_action(action='testing_related_method', b=4)
    def testing_related_action__kwargs(self):
        return

    @job
    @related_action(action='testing_related__url',
                    url='https://en.wikipedia.org/wiki/{subject}')
    def testing_related_action__store(self):
        return
