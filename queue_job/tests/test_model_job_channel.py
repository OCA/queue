# copyright 2018 Camptocamp
# license lgpl-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from unittest import mock

from psycopg2 import IntegrityError

import odoo
from odoo import exceptions
from odoo.tests import common

from odoo.addons.queue_job.jobrunner import runner


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
        # before the line 'self.env.flush_all()'. So, we are expecting an IntegrityError
        try:
            self.env.flush_all()
        except IntegrityError as ex:
            self.assertIn("queue_job_channel_name_uniq", ex.pgerror)
        else:
            self.assertEqual(True, False)

    def test_channel_display_name(self):
        channel = self.Channel.create(
            {"name": "test", "parent_id": self.root_channel.id}
        )
        self.assertEqual(channel.display_name, channel.complete_name)

    def test_capacity_should_not_be_negative(self):
        with self.assertRaisesRegex(
            exceptions.ValidationError,
            "The capacity of a channel cannot be negative.",
        ):
            self.Channel.create(
                {
                    "name": "test_capacity",
                    "parent_id": self.root_channel.id,
                    "capacity": -1,
                }
            )

    def test_capacity_default_should_not_be_negative(self):
        with self.assertRaisesRegex(
            exceptions.ValidationError,
            "The default capacity of a channel cannot be negative.",
        ):
            self.Channel.create(
                {
                    "name": "test_capacity_default",
                    "parent_id": self.root_channel.id,
                    "capacity_default": -1,
                }
            )

    def test_throttle_should_not_be_negative(self):
        with self.assertRaisesRegex(
            exceptions.ValidationError,
            "The throttle of a channel cannot be negative.",
        ):
            self.Channel.create(
                {
                    "name": "test_throttle",
                    "parent_id": self.root_channel.id,
                    "throttle": -1,
                }
            )

    def test_sequential_should_have_capacity_one(self):
        with self.assertRaisesRegex(
            exceptions.ValidationError,
            "A sequential channel must have a capacity of 1.",
        ):
            self.Channel.create(
                {
                    "name": "test_sequential",
                    "parent_id": self.root_channel.id,
                    "sequential": True,
                    "capacity": 2,
                }
            )

    def test_sequential_default_should_have_capacity_default_one(self):
        with self.assertRaisesRegex(
            exceptions.ValidationError,
            "A channel with a sequential default must have a default capacity of 1.",
        ):
            self.Channel.create(
                {
                    "name": "test_sequential_default",
                    "parent_id": self.root_channel.id,
                    "sequential_default": True,
                    "capacity_default": 2,
                }
            )

    def test_effective_capacity_root(self):
        with (
            mock.patch.object(runner, "_max_capacity", lambda: 42),
            mock.patch.object(runner, "_db_max_capacity", lambda: ""),
        ):
            self.root_channel.capacity = 5
            self.assertEqual(self.root_channel.effective_capacity, 5)

            self.root_channel.capacity = 0
            self.assertEqual(self.root_channel.effective_capacity, 42)

    def test_effective_capacity_subchannel(self):
        with (
            # the root channel is restrained to _max_capacity, ensure
            # it is high enough for the test
            mock.patch.object(runner, "_max_capacity", lambda: 100),
            mock.patch.object(runner, "_db_max_capacity", lambda: ""),
        ):
            self.root_channel.capacity = 33

            channel = self.Channel.create(
                {"name": "test", "parent_id": self.root_channel.id, "capacity": 0}
            )

            self.assertEqual(channel.effective_capacity, 33)

            subchannel = self.Channel.create(
                {"name": "test", "parent_id": channel.id, "capacity": 0}
            )
            self.assertEqual(subchannel.effective_capacity, 33)

            channel.capacity = 18

            self.assertEqual(channel.effective_capacity, 18)
            self.assertEqual(subchannel.effective_capacity, 18)

    def test_effective_paused(self):
        channel = self.Channel.create(
            {"name": "test", "parent_id": self.root_channel.id}
        )
        subchannel = self.Channel.create({"name": "test", "parent_id": channel.id})

        self.assertFalse(channel.effective_paused)
        self.assertFalse(subchannel.effective_paused)

        channel.paused = True

        self.assertTrue(channel.effective_paused)
        self.assertTrue(subchannel.effective_paused)

    def test_action_pause(self):
        self.root_channel.action_pause()
        self.assertTrue(self.root_channel.paused)

    def test_action_resume(self):
        self.root_channel.paused = True
        self.root_channel.action_resume()
        self.assertFalse(self.root_channel.paused)

    def _patch_notify(self):
        return mock.patch.object(
            type(self.Channel), "_notify_channel_config_changed", autospec=True
        )

    def test_notify_create_channel(self):
        with self._patch_notify() as notify:
            self.Channel.create(
                {
                    "name": "create_notify",
                    "parent_id": self.root_channel.id,
                    "capacity": 2,
                }
            )
        notify.assert_called_once()

    def test_notify_write_jobrunner_config(self):
        channel = self.Channel.create(
            {"name": "write_notify", "parent_id": self.root_channel.id}
        )
        with self._patch_notify() as notify:
            channel.capacity = 3
        notify.assert_called_once()

        with self._patch_notify() as notify:
            channel.paused = True
        notify.assert_called_once()

        with self._patch_notify() as notify:
            channel.removal_interval = 60
        notify.assert_not_called()

        with self._patch_notify() as notify:
            channel.capacity_default = 1
        notify.assert_called_once()

        with self._patch_notify() as notify:
            channel.sequential_default = True
        notify.assert_called_once()

    def test_notify_unlink_channel(self):
        channel = self.Channel.create(
            {"name": "unlink_notify", "parent_id": self.root_channel.id}
        )
        with self._patch_notify() as notify:
            channel.unlink()
        notify.assert_called_once()
