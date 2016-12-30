# -*- coding: utf-8 -*-
# Copyright 2014-2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import odoo.tests.common as common
from odoo.addons.queue_job.job import Job


class TestRelatedAction(common.TransactionCase):
    """ Test Related Actions """

    def setUp(self):
        super(TestRelatedAction, self).setUp()
        self.model = self.env['test.related.action']
        self.method = self.env['test.queue.job'].testing_method

    def test_return(self):
        """ Job with related action check if action returns correctly """
        job = Job(self.method)
        act_job, act_kwargs = job.related_action()
        self.assertEqual(act_job, job.db_record())
        self.assertEqual(act_kwargs, {})

    def test_no_related_action(self):
        """ Job without related action """
        job = Job(self.model.testing_related_action__no)
        self.assertIsNone(job.related_action())

    def test_return_none(self):
        """ Job with related action returning None """
        # default action returns None
        job = Job(self.model.testing_related_action__return_none)
        self.assertIsNone(job.related_action())

    def test_kwargs(self):
        """ Job with related action check if action propagates kwargs """
        job_ = Job(self.model.testing_related_action__kwargs)
        self.assertEqual(job_.related_action(), (job_.db_record(), {'b': 4}))

    def test_store_related_action(self):
        """ Call the related action on the model """
        job = Job(self.model.testing_related_action__store,
                  args=('Discworld',))
        job.store()
        stored_job = self.env['queue.job'].search(
            [('uuid', '=', job.uuid)]
        )
        self.assertEqual(len(stored_job), 1)
        expected = {'type': 'ir.actions.act_url',
                    'target': 'new',
                    'url': 'https://en.wikipedia.org/wiki/Discworld',
                    }
        self.assertEquals(stored_job.open_related_action(), expected)
