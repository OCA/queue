# -*- coding: utf-8 -*-

import unittest
from odoo.addons.queue_job.job import Job


class JobCounter(object):

    def __init__(self, env):
        super(JobCounter, self).__init__()
        self.env = env
        self.existing = self.search_all()

    def count_all(self):
        return len(self.search_all())

    def count_created(self):
        return len(self.search_created())

    def count_existing(self):
        return len(self.existing)

    def search_created(self):
        return self.search_all() - self.existing

    def search_all(self):
        return self.env['queue.job'].search([])


class JobMixin(unittest.TestCase):

    def job_counter(self):
        return JobCounter(self.env)

    def perform_jobs(self, jobs):
        for job in jobs.search_created():
            Job.load(self.env, job.uuid).perform()
