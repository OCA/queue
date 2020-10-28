# Copyright 2020 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo.addons.queue_job.job import Job

from .common import JobCommonCase


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
        result = (
            self.env["test.queue.job"]
            .with_context(_job_force_sync=True)
            .delay_me(1, kwarg=2)
        )
        self.assertTrue(result, (1, 2))
