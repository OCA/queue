# Copyright 2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.queue_job.exception import RetryableJobError


class QueueJob(models.Model):

    _inherit = "queue.job"

    def testing_related_method(self, **kwargs):
        return self, kwargs

    def testing_related__none(self, **kwargs):
        return None

    def testing_related__url(self, **kwargs):
        assert "url" in kwargs, "url required"
        subject = self.args[0]
        return {
            "type": "ir.actions.act_url",
            "target": "new",
            "url": kwargs["url"].format(subject=subject),
        }


class TestQueueJob(models.Model):

    _name = "test.queue.job"
    _description = "Test model for queue.job"

    name = fields.Char()

    def testing_method(self, *args, **kwargs):
        """Method used for tests

        Return always the arguments and keyword arguments received
        """
        if kwargs.get("raise_retry"):
            raise RetryableJobError("Must be retried later")
        if kwargs.get("return_context"):
            return self.env.context
        return args, kwargs

    def test_long_running_method(self):
        self.env.cr.execute("""select pg_sleep(5 * 60);""")
        raise UserError(_("Sleep was not interrupted."))

    def no_description(self):
        return

    def job_with_retry_pattern(self):
        return

    def job_with_retry_pattern__no_zero(self):
        return

    def mapped(self, func):
        return super(TestQueueJob, self).mapped(func)

    def job_alter_mutable(self, mutable_arg, mutable_kwarg=None):
        mutable_arg.append(2)
        mutable_kwarg["b"] = 2
        return mutable_arg, mutable_kwarg


class TestQueueChannel(models.Model):

    _name = "test.queue.channel"
    _description = "Test model for queue.channel"

    def job_a(self):
        return

    def job_b(self):
        return

    def job_sub_channel(self):
        return


class TestRelatedAction(models.Model):

    _name = "test.related.action"
    _description = "Test model for related actions"

    def testing_related_action__no(self):
        return

    def testing_related_action__return_none(self):
        return

    def testing_related_action__kwargs(self):
        return

    def testing_related_action__store(self):
        return
