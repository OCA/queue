# copyright 2018 Camptocamp
# license agpl-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from psycopg2 import IntegrityError

import odoo

from odoo.tests import common


class TestJobChannel(common.TransactionCase):

    def setUp(self):
        super(TestJobChannel, self).setUp()
        self.Channel = self.env['queue.job.channel']
        self.root_channel = self.Channel.search(
            [('name', '=', 'root')]
        )

    def test_channel_new(self):
        channel = self.Channel.new()
        self.assertFalse(channel.name)
        self.assertFalse(channel.complete_name)

    def test_channel_create(self):
        channel = self.Channel.create({
            'name': 'sub',
            'parent_id': self.root_channel.id,
        })
        self.assertEqual(channel.name, 'sub')
        self.assertEqual(channel.complete_name, 'root.sub')
        channel2 = self.Channel.create({
            'name': 'sub',
            'parent_id': channel.id,
        })
        self.assertEqual(channel2.name, 'sub')
        self.assertEqual(channel2.complete_name, 'root.sub.sub')

    @odoo.tools.mute_logger('odoo.sql_db')
    def test_channel_complete_name_uniq(self):
        channel = self.Channel.create({
            'name': 'sub',
            'parent_id': self.root_channel.id,
        })
        self.assertEqual(channel.name, 'sub')
        self.assertEqual(channel.complete_name, 'root.sub')

        with self.assertRaises(IntegrityError):
            self.Channel.create({
                'name': 'sub',
                'parent_id': self.root_channel.id,
            })

    def test_channel_name_get(self):
        channel = self.Channel.create({
            'name': 'sub',
            'parent_id': self.root_channel.id,
        })
        self.assertEqual(channel.name_get(), [(channel.id, 'root.sub')])
