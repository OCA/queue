# -*- coding: utf-8 -*-

import mock
import unittest

import odoo.tests.common as common
from odoo.addons.queue_job.job import Job, related_action
from .common import start_jobify, stop_jobify


def task_no_related(env):
    pass


def task_related_none(env):
    pass


def task_related_return(env):
    pass


def task_related_return_kwargs(env):
    pass


def open_url(env, job, url=None):
    subject = job.args[0]
    return {
        'type': 'ir.actions.act_url',
        'target': 'new',
        'url': url.format(subject=subject),
    }


# @related_action(action=open_url, url='https://en.wikipedia.org/wiki/{subject}')
# def task_wikipedia(env, subject):
#     pass


class TestRelatedAction(common.TransactionCase):
    """ Test Related Actions """

    def setUp(self):
        super(TestRelatedAction, self).setUp()
        self.method = self.env['queue.job'].testing_method
        start_jobify(self.method)

    def tearDown(self):
        super(TestRelatedAction, self).tearDown()
        stop_jobify(self.method)

    def test_no_related_action(self):
        """ Job without related action """
        job = Job(self.method)
        self.assertIsNone(job.related_action(self.env))

    @unittest.skip('to reimplement')
    def test_return_none(self):
        """ Job with related action returning None """
        # default action returns None
        job = Job(self.env, func=related_action()(task_related_none))
        self.assertIsNone(job.related_action(self.env))

    @unittest.skip('to reimplement')
    def test_return(self):
        """ Job with related action check if action returns correctly """
        def action(env, job):
            return env, job
        job = Job(self.env,
                  func=related_action(action=action)(task_related_return))
        act_env, act_job = job.related_action(self.env)
        self.assertEqual(act_env, self.env)
        self.assertEqual(act_job, job)

    @unittest.skip('to reimplement')
    def test_kwargs(self):
        """ Job with related action check if action propagates kwargs """
        def action(env, job, a=1, b=2):
            return a, b
        task = task_related_return_kwargs
        job_func = related_action(action=action, b=4)(task)
        job = Job(self.env, func=job_func)
        self.assertEqual(job.related_action(self.env), (1, 4))

    @unittest.skip('to reimplement on model methods')
    def test_store_related_action(self):
        """ Call the related action on the model """
        job = Job(self.env, func=task_wikipedia, args=('Discworld',))
        job.store()
        stored_job = self.queue_job.search([('uuid', '=', job.uuid)])
        self.assertEqual(len(stored_job), 1)
        expected = {'type': 'ir.actions.act_url',
                    'target': 'new',
                    'url': 'https://en.wikipedia.org/wiki/Discworld',
                    }
        self.assertEquals(stored_job.open_related_action(), expected)

    @unittest.skip('to reimplement')
    def test_related_action_model_method(self):
        """ Related action on model method """
        try:
            related_action(action=task_related_return)(
                self.env['res.users'].preference_save
            )
            self.assertEquals(
                self.env['res.users'].preference_save.related_action,
                task_related_return
            )
        finally:
            method = self.env['res.users'].preference_save
            if hasattr(method.__func__, 'related_action'):
                del method.__func__.related_action
