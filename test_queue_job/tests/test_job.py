# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from datetime import datetime
import mock

import odoo.tests.common as common

from odoo.addons.queue_job.job import (
    Job,
    RETRY_INTERVAL,
)


class TestJobs(common.TransactionCase):
    """ Test jobs on other methods or with different job configuration """

    def test_description(self):
        """ If no description is given to the job, it
        should be computed from the function
        """
        # if a docstring is defined for the function
        # it's used as description
        job_a = Job(self.env['queue.job'].testing_method)
        self.assertEqual(job_a.description, "Method used for tests")
        # if no docstring, the description is computed
        job_b = Job(self.env['test.queue.job'].no_description)
        self.assertEqual(job_b.description, "test.queue.job.no_description")
        # case when we explicitly specify the description
        description = "My description"
        job_a = Job(self.env['queue.job'].testing_method,
                    description=description)
        self.assertEqual(job_a.description, description)

    def test_retry_pattern(self):
        """ When we specify a retry pattern, the eta must follow it"""
        datetime_path = 'odoo.addons.queue_job.job.datetime'
        method = self.env['test.queue.job'].job_with_retry_pattern
        with mock.patch(datetime_path, autospec=True) as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2015, 6, 1, 15, 10, 0
            )
            test_job = Job(method, max_retries=0)
            test_job.retry += 1
            test_job.postpone(self.env)
            self.assertEqual(test_job.retry, 1)
            self.assertEqual(test_job.eta,
                             datetime(2015, 6, 1, 15, 11, 0))
            test_job.retry += 1
            test_job.postpone(self.env)
            self.assertEqual(test_job.retry, 2)
            self.assertEqual(test_job.eta,
                             datetime(2015, 6, 1, 15, 13, 0))
            test_job.retry += 1
            test_job.postpone(self.env)
            self.assertEqual(test_job.retry, 3)
            self.assertEqual(test_job.eta,
                             datetime(2015, 6, 1, 15, 10, 10))
            test_job.retry += 1
            test_job.postpone(self.env)
            self.assertEqual(test_job.retry, 4)
            self.assertEqual(test_job.eta,
                             datetime(2015, 6, 1, 15, 10, 10))
            test_job.retry += 1
            test_job.postpone(self.env)
            self.assertEqual(test_job.retry, 5)
            self.assertEqual(test_job.eta,
                             datetime(2015, 6, 1, 15, 15, 0))

    def test_retry_pattern_no_zero(self):
        """ When we specify a retry pattern without 0, uses RETRY_INTERVAL"""
        method = self.env['test.queue.job'].job_with_retry_pattern__no_zero
        test_job = Job(method, max_retries=0)
        test_job.retry += 1
        self.assertEqual(test_job.retry, 1)
        self.assertEqual(test_job._get_retry_seconds(), RETRY_INTERVAL)
        test_job.retry += 1
        self.assertEqual(test_job.retry, 2)
        self.assertEqual(test_job._get_retry_seconds(), RETRY_INTERVAL)
        test_job.retry += 1
        self.assertEqual(test_job.retry, 3)
        self.assertEqual(test_job._get_retry_seconds(), 180)
        test_job.retry += 1
        self.assertEqual(test_job.retry, 4)
        self.assertEqual(test_job._get_retry_seconds(), 180)

    def test_job_delay_model_method_multi(self):
        rec1 = self.env['test.queue.job'].create({'name': 'test1'})
        rec2 = self.env['test.queue.job'].create({'name': 'test2'})
        recs = rec1 + rec2
        job_instance = recs.with_delay().mapped('name')
        self.assertTrue(job_instance)
        self.assertEquals(job_instance.args, ('name',))
        self.assertEquals(job_instance.recordset, recs)
        self.assertEquals(job_instance.model_name, 'test.queue.job')
        self.assertEquals(job_instance.method_name, 'mapped')
        self.assertEquals(['test1', 'test2'], job_instance.perform())
