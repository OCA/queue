# Copyright 2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import odoo.tests.common as common
from odoo import exceptions

from odoo.addons.queue_job.job import Job


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
        self.assertEqual(channel.complete_name, "root.number")
        self.assertEqual(subchannel.complete_name, "root.number.five")

    def test_channel_tree(self):
        with self.assertRaises(exceptions.ValidationError):
            self.channel_model.create({"name": "sub"})

    def test_channel_root(self):
        with self.assertRaises(exceptions.UserError):
            self.root_channel.unlink()
        with self.assertRaises(exceptions.UserError):
            self.root_channel.name = "leaf"

    def test_channel_on_job(self):
        method = self.env["test.queue.channel"].job_a
        path_a = self.env["queue.job.function"].job_function_name(
            "test.queue.channel", "job_a"
        )
        job_func = self.function_model.search([("name", "=", path_a)])

        self.assertEqual(job_func.channel, "root")

        test_job = Job(method)
        test_job.store()
        stored = test_job.db_record()
        self.assertEqual(stored.channel, "root")
        job_read = Job.load(self.env, test_job.uuid)
        self.assertEqual(job_read.channel, "root")

        sub_channel = self.env.ref("test_queue_job.channel_sub")
        job_func.channel_id = sub_channel

        test_job = Job(method)
        test_job.store()
        stored = test_job.db_record()
        self.assertEqual(stored.channel, "root.sub")

        # it's also possible to override the channel
        test_job = Job(method, channel="root.sub")
        test_job.store()
        stored = test_job.db_record()
        self.assertEqual(stored.channel, test_job.channel)

    def test_default_channel_no_xml(self):
        """Channel on job is root if there is no queue.job.function record"""
        test_job = Job(self.env["res.users"].browse)
        test_job.store()
        stored = test_job.db_record()
        self.assertEqual(stored.channel, "root")

    def test_set_channel_from_record(self):
        func_name = self.env["queue.job.function"].job_function_name(
            "test.queue.channel", "job_sub_channel"
        )
        job_func = self.function_model.search([("name", "=", func_name)])
        self.assertEqual(job_func.channel, "root.sub.subsub")

        channel = job_func.channel_id
        self.assertEqual(channel.name, "subsub")
        self.assertEqual(channel.parent_id.name, "sub")
        self.assertEqual(channel.parent_id.parent_id.name, "root")
        self.assertEqual(job_func.channel, "root.sub.subsub")

    def test_default_removal_interval(self):
        channel = self.channel_model.create(
            {"name": "number", "parent_id": self.root_channel.id}
        )
        self.assertEqual(channel.removal_interval, 30)
