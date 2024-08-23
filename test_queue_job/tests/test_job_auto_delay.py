# Copyright 2020 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo.tests.common import tagged

from odoo.addons.queue_job.job import Job

from .common import JobCommonCase


@tagged("post_install", "-at_install")
class TestJobAutoDelay(JobCommonCase):
    """Test auto delay of jobs"""

    def test_auto_delay(self):
        """method decorated by @job_auto_delay is automatically delayed"""
        result = self.env["test.queue.job"].delay_me(1, kwarg=2)
        self.assertTrue(isinstance(result, Job))
        self.assertEqual(result.args, (1,))
        self.assertEqual(result.kwargs, {"kwarg": 2})

    def test_auto_delay_options(self):
        """method automatically delayed une <method>_job_options arguments"""
        result = self.env["test.queue.job"].delay_me_options()
        self.assertTrue(isinstance(result, Job))
        self.assertEqual(result.identity_key, "my_job_identity")

    def test_auto_delay_inside_job(self):
        """when a delayed job is processed, it must not delay itself"""
        job_ = self.env["test.queue.job"].delay_me(1, kwarg=2)
        self.assertTrue(job_.perform(), (1, 2))

    def test_auto_delay_force_sync(self):
        """method forced to run synchronously"""
        with self.assertLogs(level="WARNING") as log_catcher:
            result = (
                self.env["test.queue.job"]
                .with_context(_job_force_sync=True)
                .delay_me(1, kwarg=2)
            )
        self.assertEqual(
            len(log_catcher.output), 1, "Exactly one warning should be logged"
        )
        self.assertIn(" ctx key found. NO JOB scheduled. ", log_catcher.output[0])
        self.assertTrue(result, (1, 2))

    def test_auto_delay_context_key_set(self):
        """patched with context_key delays only if context keys is set"""
        result = (
            self.env["test.queue.job"]
            .with_context(auto_delay_delay_me_context_key=True)
            .delay_me_context_key()
        )
        self.assertTrue(isinstance(result, Job))

    def test_auto_delay_context_key_unset(self):
        """patched with context_key do not delay if context keys is not set"""
        result = self.env["test.queue.job"].delay_me_context_key()
        self.assertEqual(result, "ok")
