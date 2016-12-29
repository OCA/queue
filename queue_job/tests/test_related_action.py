# -*- coding: utf-8 -*-
# Copyright 2014-2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import odoo.tests.common as common
from odoo.addons.queue_job.job import Job


class TestRelatedAction(common.TransactionCase):
    """ Test Related Actions """

    def setUp(self):
        super(TestRelatedAction, self).setUp()
        self.method = self.env['queue.job'].testing_method

    def test_return(self):
        """ Job with related action check if action returns correctly """
        job = Job(self.method)
        act_job, act_kwargs = job.related_action()
        self.assertEqual(act_job, job.db_record())
        self.assertEqual(act_kwargs, {})
