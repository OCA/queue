# Copyright 2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import api, fields, models

from odoo.addons.queue_job.delay import chain
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.addons.queue_job.job import identity_exact


class QueueJob(models.Model):

    _inherit = "queue.job"

    additional_info = fields.Char()

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


class ModelTestQueueJob(models.Model):

    _name = "test.queue.job"
    _description = "Test model for queue.job"

    name = fields.Char()

    # to test the context is serialized/deserialized properly
    @api.model
    def _job_prepare_context_before_enqueue_keys(self):
        return ("tz", "lang")

    def testing_method(self, *args, **kwargs):
        """Method used for tests

        Return always the arguments and keyword arguments received
        """
        if kwargs.get("raise_retry"):
            raise RetryableJobError("Must be retried later")
        if kwargs.get("return_context"):
            return self.env.context
        return args, kwargs

    def create_ir_logging(self, message, level="info"):
        return self.env["ir.logging"].create(
            {
                "name": "test_queue_job",
                "type": "server",
                "dbname": self.env.cr.dbname,
                "message": message,
                "path": "job",
                "func": "create_ir_logging",
                "line": 1,
            }
        )

    def no_description(self):
        return

    def job_with_retry_pattern(self):
        return

    def job_with_retry_pattern__no_zero(self):
        return

    def mapped(self, func):
        return super(ModelTestQueueJob, self).mapped(func)

    def job_alter_mutable(self, mutable_arg, mutable_kwarg=None):
        mutable_arg.append(2)
        mutable_kwarg["b"] = 2
        return mutable_arg, mutable_kwarg

    def delay_me(self, arg, kwarg=None):
        return arg, kwarg

    def delay_me_options_job_options(self):
        return {
            "identity_key": "my_job_identity",
        }

    def delay_me_options(self):
        return "ok"

    def delay_me_context_key(self):
        return "ok"

    def _register_hook(self):
        self._patch_method("delay_me", self._patch_job_auto_delay("delay_me"))
        self._patch_method(
            "delay_me_options", self._patch_job_auto_delay("delay_me_options")
        )
        self._patch_method(
            "delay_me_context_key",
            self._patch_job_auto_delay(
                "delay_me_context_key", context_key="auto_delay_delay_me_context_key"
            ),
        )
        return super()._register_hook()

    def _job_store_values(self, job):
        value = "JUST_TESTING"
        if job.state == "failed":
            value += "_BUT_FAILED"
        return {"additional_info": value}

    def button_that_uses_with_delay(self):
        self.with_delay(
            channel="root.test",
            description="Test",
            eta=15,
            identity_key=identity_exact,
            max_retries=1,
            priority=15,
        ).testing_method(1, foo=2)

    def button_that_uses_delayable_chain(self):
        delayables = chain(
            self.delayable(
                channel="root.test",
                description="Test",
                eta=15,
                identity_key=identity_exact,
                max_retries=1,
                priority=15,
            ).testing_method(1, foo=2),
            self.delayable().testing_method("x", foo="y"),
            self.delayable().no_description(),
        )
        delayables.delay()


class ModelTestQueueChannel(models.Model):

    _name = "test.queue.channel"
    _description = "Test model for queue.channel"

    def job_a(self):
        return

    def job_b(self):
        return

    def job_sub_channel(self):
        return


class ModelTestRelatedAction(models.Model):

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
