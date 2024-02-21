# copyright 2018 Camptocamp
# license lgpl-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from psycopg2 import IntegrityError

import odoo
from odoo.tests import common


class TestJobChannel(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Remove this variable in v16 and put instead:
        # from odoo.addons.base.tests.common import DISABLED_MAIL_CONTEXT
        DISABLED_MAIL_CONTEXT = {
            "tracking_disable": True,
            "mail_create_nolog": True,
            "mail_create_nosubscribe": True,
            "mail_notrack": True,
            "no_reset_password": True,
        }
        cls.env = cls.env(context=dict(cls.env.context, **DISABLED_MAIL_CONTEXT))
        cls.Channel = cls.env["queue.job.channel"]
        cls.root_channel = cls.Channel.search([("name", "=", "root")])

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
        # not uses here due to its 'flush()' method inside it and exception raises
        # before the line 'self.env["base"].flush()'. So, we are expecting an IntegrityError.
        try:
            self.env["base"].flush()
        except IntegrityError as ex:
            self.assertIn("queue_job_channel_name_uniq", ex.pgerror)
        else:
            self.assertEqual(True, False)

    def test_channel_name_get(self):
        channel = self.Channel.create(
            {"name": "test", "parent_id": self.root_channel.id}
        )
        self.assertEqual(channel.name_get(), [(channel.id, "root.test")])
