# Copyright 2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import odoo.tests.common as common
from odoo import exceptions

from odoo.addons.queue_job.job import Job, job


class TestJobChannels(common.TransactionCase):
    def setUp(self):
        super(TestJobChannels, self).setUp()
        self.function_model = self.env["queue.job.function"]
        self.channel_model = self.env["queue.job.channel"]
        self.test_model = self.env["test.queue.channel"]
        self.root_channel = self.env.ref("queue_job.channel_root")

    def test_channel_complete_name(self):
        channel = self.channel_model.create(
            {"name": "number", "parent_id": self.root_channel.id}
        )
        subchannel = self.channel_model.create(
            {"name": "five", "parent_id": channel.id}
        )
        self.assertEquals(channel.complete_name, "root.number")
        self.assertEquals(subchannel.complete_name, "root.number.five")

    def test_channel_tree(self):
        with self.assertRaises(exceptions.ValidationError):
            self.channel_model.create({"name": "sub"})

    def test_channel_root(self):
        with self.assertRaises(exceptions.Warning):
            self.root_channel.unlink()
        with self.assertRaises(exceptions.Warning):
            self.root_channel.name = "leaf"

    def test_register_jobs(self):
        self.env["queue.job.function"].search([]).unlink()
        self.env["queue.job.channel"].search([("name", "!=", "root")]).unlink()

        method_a = self.env["test.queue.channel"].job_a
        self.env["queue.job.function"]._register_job(
            self.env["test.queue.channel"], method_a
        )
        method_b = self.env["test.queue.channel"].job_b
        self.env["queue.job.function"]._register_job(
            self.env["test.queue.channel"], method_b
        )

        path_a = "<test.queue.channel>.job_a"
        path_b = "<test.queue.channel>.job_b"
        self.assertTrue(self.function_model.search([("name", "=", path_a)]))
        self.assertTrue(self.function_model.search([("name", "=", path_b)]))

    def test_channel_on_job(self):
        self.env["queue.job.function"].search([]).unlink()
        self.env["queue.job.channel"].search([("name", "!=", "root")]).unlink()

        method = self.env["test.queue.channel"].job_a
        self.env["queue.job.function"]._register_job(
            self.env["test.queue.channel"], method
        )
        path_a = "<{}>.{}".format(method.__self__.__class__._name, method.__name__)
        job_func = self.function_model.search([("name", "=", path_a)])
        self.assertEquals(job_func.channel, "root")

        test_job = Job(method)
        test_job.store()
        stored = self.env["queue.job"].search([("uuid", "=", test_job.uuid)])
        self.assertEquals(stored.channel, "root")
        job_read = Job.load(self.env, test_job.uuid)
        self.assertEquals(job_read.channel, "root")

        channel = self.channel_model.create(
            {"name": "sub", "parent_id": self.root_channel.id}
        )
        job_func.channel_id = channel

        test_job = Job(method)
        test_job.store()
        stored = self.env["queue.job"].search([("uuid", "=", test_job.uuid)])
        self.assertEquals(stored.channel, "root.sub")

        # it's also possible to override the channel
        test_job = Job(method, channel="root.sub.sub.sub")
        test_job.store()
        stored = self.env["queue.job"].search([("uuid", "=", test_job.uuid)])
        self.assertEquals(stored.channel, test_job.channel)

    def test_default_channel(self):
        self.env["queue.job.function"].search([]).unlink()
        self.env["queue.job.channel"].search([("name", "!=", "root")]).unlink()

        method = self.env["test.queue.channel"].job_sub_channel
        self.env["queue.job.function"]._register_job(
            self.env["test.queue.channel"], method
        )
        self.assertEquals(method.default_channel, "root.sub.subsub")

        path_a = "<{}>.{}".format(method.__self__.__class__._name, method.__name__)
        job_func = self.function_model.search([("name", "=", path_a)])

        channel = job_func.channel_id
        self.assertEquals(channel.name, "subsub")
        self.assertEquals(channel.parent_id.name, "sub")
        self.assertEquals(channel.parent_id.parent_id.name, "root")
        self.assertEquals(job_func.channel, "root.sub.subsub")

    def test_job_decorator(self):
        """ Test the job decorator """
        default_channel = "channel"
        retry_pattern = {1: 5}
        partial = job(
            None, default_channel=default_channel, retry_pattern=retry_pattern
        )
        self.assertEquals(partial.keywords.get("default_channel"), default_channel)
        self.assertEquals(partial.keywords.get("retry_pattern"), retry_pattern)

    def test_default_removal_interval(self):
        channel = self.channel_model.create(
            {"name": "number", "parent_id": self.root_channel.id}
        )
        self.assertEqual(channel.removal_interval, 30)
