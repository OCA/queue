# Copyright 2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import odoo.tests.common as common

from odoo.addons.queue_job.job import (
    Job,
)


class TestJobDependencies(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.queue_job = self.env['queue.job']
        self.method = self.env['test.queue.job'].testing_method

    def test_depends_store(self):
        job_root = Job(self.method)
        job_lvl1_a = Job(self.method)
        job_lvl1_a.add_depends({job_root})
        job_lvl1_b = Job(self.method)
        job_lvl1_b.add_depends({job_root})
        job_lvl2_a = Job(self.method)
        job_lvl2_a.add_depends({job_lvl1_a})

        # Jobs must be stored after the dependencies are set up.
        # (Or if not, a new store must be called on the parent)
        job_root.store()
        job_lvl1_a.store()
        job_lvl1_b.store()
        job_lvl2_a.store()

        # test properties
        self.assertFalse(job_root.depends_on)

        self.assertEqual(job_lvl1_a.depends_on, {job_root})
        self.assertEqual(job_lvl1_b.depends_on, {job_root})

        self.assertEqual(job_lvl2_a.depends_on, {job_lvl1_a})

        self.assertEqual(job_root.reverse_depends_on, {job_lvl1_a, job_lvl1_b})

        self.assertEqual(job_lvl1_a.reverse_depends_on, {job_lvl2_a})
        self.assertFalse(job_lvl1_b.reverse_depends_on)

        self.assertFalse(job_lvl2_a.reverse_depends_on)

        # test DB state
        self.assertEqual(job_root.db_record().dependencies['depends_on'], [])
        self.assertEqual(
            sorted(job_root.db_record().dependencies['reverse_depends_on']),
            sorted([job_lvl1_a.uuid, job_lvl1_b.uuid])
        )

        self.assertEqual(
            job_lvl1_a.db_record().dependencies['depends_on'], [job_root.uuid]
        )
        self.assertEqual(
            job_lvl1_a.db_record().dependencies['reverse_depends_on'],
            [job_lvl2_a.uuid]
        )

        self.assertEqual(
            job_lvl1_b.db_record().dependencies['depends_on'], [job_root.uuid]
        )
        self.assertEqual(
            job_lvl1_b.db_record().dependencies['reverse_depends_on'], []
        )

        self.assertEqual(
            job_lvl2_a.db_record().dependencies['depends_on'],
            [job_lvl1_a.uuid]
        )
        self.assertEqual(
            job_lvl2_a.db_record().dependencies['reverse_depends_on'], []
        )

    def test_depends_store_after(self):
        job_root = Job(self.method)
        job_root.store()
        job_a = Job(self.method)
        job_a.add_depends({job_root})
        job_a.store()

        # as the reverse dependency has been added after the root job has been
        # stored, it is not reflected in DB
        self.assertEqual(
            job_root.db_record().dependencies['reverse_depends_on'], []
        )

        # a new store will write it
        job_root.store()
        self.assertEqual(
            job_root.db_record().dependencies['reverse_depends_on'],
            [job_a.uuid]
        )

    def test_depends_load(self):
        job_root = Job(self.method)
        job_a = Job(self.method)
        job_a.add_depends({job_root})

        job_root.store()
        job_a.store()

        read_job_root = Job.load(self.env, job_root.uuid)
        self.assertEqual(read_job_root.reverse_depends_on, {job_a})

        read_job_a = Job.load(self.env, job_a.uuid)
        self.assertEqual(read_job_a.depends_on, {job_root})
