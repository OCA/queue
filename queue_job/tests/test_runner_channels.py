# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import os
from unittest.mock import patch

from odoo.tests import BaseCase

# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
from odoo.addons.queue_job.jobrunner import channels

from .common import load_doctests

load_tests = load_doctests(channels)


class TestDefaultSubchannelCapacity(BaseCase):
    @patch.dict(os.environ, {"ODOO_QUEUE_JOB_DEFAULT_SUBCHANNEL_CAPACITY": "1"})
    def test_default_subchannel_capacity_env(self):
        self.assertEqual(channels._default_subchannel_capacity(), 1)

    @patch.dict(channels.queue_job_config, {"default_subchannel_capacity": "1"})
    def test_default_subchannel_capacity_conf(self):
        self.assertEqual(channels._default_subchannel_capacity(), 1)

    def test_default_subchannel_capacity_omit(self):
        self.assertIs(channels._default_subchannel_capacity(), None)
