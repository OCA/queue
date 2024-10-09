# copyright 2018 Camptocamp
# license lgpl-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import uuid
from datetime import timedelta

from psycopg2 import IntegrityError

import odoo
from odoo.tests import common


class TestJobChannel(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.Channel = self.env["queue.job.channel"]
        self.root_channel = self.Channel.search([("name", "=", "root")])

    def test_channel_new(self):
        channel = self.Channel.new()
        self.assertFalse(channel.name)
        self.assertFalse(channel.complete_name)

    def test_channel_create(self):
        channel = self.Channel.create(
            {"name": "test", "parent_id": self.root_channel.id}
        )
        self.assertEqual(channel.name, "test")
        self.assertEqual(channel.complete_name, "root.test")
        channel2 = self.Channel.create({"name": "test", "parent_id": channel.id})
        self.assertEqual(channel2.name, "test")
        self.assertEqual(channel2.complete_name, "root.test.test")

    @odoo.tools.mute_logger("odoo.sql_db")
    def test_channel_complete_name_uniq(self):
        channel = self.Channel.create(
            {"name": "test", "parent_id": self.root_channel.id}
        )
        self.assertEqual(channel.name, "test")
        self.assertEqual(channel.complete_name, "root.test")

        self.Channel.create({"name": "test", "parent_id": self.root_channel.id})

        # Flush process all the pending recomputations (or at least the
        # given field and flush the pending updates to the database.
        # It is normally called on commit.

        # The context manager 'with self.assertRaises(IntegrityError)' purposefully
        # not uses here due to its 'flush_all()' method inside it and exception raises
        # before the line 'self.env.flush_all()'. So, we are expecting an IntegrityError.
        try:
            self.env.flush_all()
        except IntegrityError as ex:
            self.assertIn("queue_job_channel_name_uniq", ex.pgerror)
        else:
            self.assertEqual(True, False)

    def test_channel_name_get(self):
        channel = self.Channel.create(
            {"name": "test", "parent_id": self.root_channel.id}
        )
        self.assertEqual(channel.name_get(), [(channel.id, "root.test")])

    def _create_job(self, channel_name):
        return (
            self.env["queue.job"]
            .with_context(
                _job_edit_sentinel=self.env["queue.job"].EDIT_SENTINEL,
            )
            .create(
                {
                    "uuid": str(uuid.uuid4()),
                    "user_id": self.env.user.id,
                    "state": "pending",
                    "model_name": "queue.job",
                    "method_name": "write",
                    "args": (),
                    "channel": channel_name,
                }
            )
        )

    def test_requeue_stuck_jobs(self):
        def _update_started_job_date(job, minutes):
            date = odoo.fields.datetime.now() - timedelta(minutes=minutes)
            job.write({"state": "started", "date_started": date})
            self.assertEqual(job.state, "started")

        def _update_enqueued_job_date(job, minutes):
            date = odoo.fields.datetime.now() - timedelta(minutes=minutes)
            job.write({"state": "enqueued", "date_enqueued": date})
            self.assertEqual(job.state, "enqueued")

        channel_1 = self.Channel.create(
            {"name": "test", "parent_id": self.root_channel.id}
        )
        channel_2 = self.Channel.create(
            {"name": "test2", "parent_id": self.root_channel.id}
        )
        job = self._create_job("root.test")
        job_2 = self._create_job("root.test2")
        self.assertEqual(job.channel, "root.test")
        self.assertEqual(job_2.channel, "root.test2")
        self.assertEqual(job.state, "pending")
        self.assertEqual(job_2.state, "pending")
        # Started
        # Global config
        _update_started_job_date(job, 10)
        _update_started_job_date(job_2, 20)
        self.env["queue.job"].requeue_stuck_jobs(enqueued_delta=0, started_delta=15)
        self.assertEqual(job.state, "started")
        self.assertEqual(job_2.state, "pending")
        # Per channel config
        _update_started_job_date(job, 10)
        _update_started_job_date(job_2, 20)
        channel_1.write({"started_delta": 5})
        channel_2.write({"started_delta": 25})
        self.env["queue.job"].requeue_stuck_jobs(enqueued_delta=0, started_delta=15)
        self.assertEqual(job.state, "pending")
        self.assertEqual(job_2.state, "started")
        # Mixed
        channel_1.write({"started_delta": 0})
        channel_2.write({"started_delta": 25})
        _update_started_job_date(job, 20)
        _update_started_job_date(job_2, 20)
        self.env["queue.job"].requeue_stuck_jobs(enqueued_delta=0, started_delta=15)
        self.assertEqual(job.state, "pending")
        self.assertEqual(job_2.state, "started")
        # Enqueued
        # Global config
        _update_enqueued_job_date(job, 10)
        _update_enqueued_job_date(job_2, 20)
        self.env["queue.job"].requeue_stuck_jobs(enqueued_delta=15, started_delta=0)
        self.assertEqual(job.state, "enqueued")
        self.assertEqual(job_2.state, "pending")
        # Per channel config
        _update_enqueued_job_date(job, 10)
        _update_enqueued_job_date(job_2, 20)
        channel_1.write({"enqueued_delta": 5})
        channel_2.write({"enqueued_delta": 25})
        self.env["queue.job"].requeue_stuck_jobs(enqueued_delta=15, started_delta=0)
        self.assertEqual(job.state, "pending")
        self.assertEqual(job_2.state, "enqueued")
        # Mixed
        channel_1.write({"enqueued_delta": 0})
        channel_2.write({"enqueued_delta": 25})
        _update_enqueued_job_date(job, 20)
        _update_enqueued_job_date(job_2, 20)
        self.env["queue.job"].requeue_stuck_jobs(enqueued_delta=15, started_delta=0)
        self.assertEqual(job.state, "pending")
        self.assertEqual(job_2.state, "enqueued")
        # job without queue.job.channel record for its channel
        # it uses the global value
        job_3 = self._create_job("root.test3")
        channel_1.write({"started_delta": 50})
        channel_2.write({"enqueued_delta": 50})
        _update_started_job_date(job, 10)
        _update_enqueued_job_date(job_2, 20)
        _update_started_job_date(job_3, 30)
        self.env["queue.job"].requeue_stuck_jobs(enqueued_delta=5, started_delta=5)
        self.assertEqual(job.state, "started")
        self.assertEqual(job_2.state, "enqueued")
        self.assertEqual(job_3.state, "pending")
