# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo.tests import BaseCase

# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
from odoo.addons.queue_job.jobrunner import channels

from .common import load_doctests

load_tests = load_doctests(channels)


class TestChannelManager(BaseCase):
    def test_subcapacity_default(self):
        cm = channels.ChannelManager()
        cm.simple_configure("root:4")
        root = cm.get_channel_by_name("root")
        self.assertEqual(root.capacity, 4)
        self.assertEqual(root.subcapacity, 0)
        child = cm.get_channel_by_name("child", autocreate=True)
        self.assertIs(child.capacity, None)
        self.assertEqual(child.subcapacity, 0)

    def test_subcapacity(self):
        cm = channels.ChannelManager()
        cm.simple_configure("root:4:subcapacity=1,override:2")
        root = cm.get_channel_by_name("root")
        self.assertEqual(root.subcapacity, 1)
        child = cm.get_channel_by_name("override")
        self.assertEqual(child.capacity, 2)
        self.assertEqual(child.subcapacity, 0)
        child = cm.get_channel_by_name("child", autocreate=True)
        self.assertEqual(child.capacity, 1)
        self.assertEqual(child.subcapacity, 0)

    def test_subcapacity_subchannel(self):
        cm = channels.ChannelManager()
        cm.simple_configure("root:4,sub:2:subcapacity=1")
        child = cm.get_channel_by_name("sub.child", autocreate=True)
        self.assertEqual(child.capacity, 1)
        self.assertEqual(child.subcapacity, 0)
