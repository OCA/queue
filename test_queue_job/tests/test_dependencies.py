# Copyright 2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import odoo.tests.common as common

from odoo.addons.queue_job.job import (
    Job,
    WAIT_DEPENDENCIES,
    PENDING,
)


class TestJobDependencies(common.SavepointCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.queue_job = cls.env['queue.job']
        cls.method = cls.env['test.queue.job'].testing_method

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

    def test_depends_enqueue_waiting_single(self):
        job_root = Job(self.method)
        job_a = Job(self.method)
        job_a.add_depends({job_root})

        job_root.store()
        job_a.store()

        self.assertEqual(job_a.state, WAIT_DEPENDENCIES)

        # these are the steps run by RunJobController
        job_root.perform()
        job_root.set_done()
        job_root.store()

        job_root.enqueue_waiting()

        # Will be picked up by the jobrunner.
        # Warning: as the state has been changed in memory but
        # not in the job_a instance, here, we re-read it.
        # In practice, it won't be an issue for the jobrunner.
        self.assertEqual(Job.load(self.env, job_a.uuid).state, PENDING)

    def test_dependency_graph(self):
        job_root = Job(self.method)
        job_lvl1_a = Job(self.method)
        job_lvl1_a.add_depends({job_root})
        job_lvl1_b = Job(self.method)
        job_lvl1_b.add_depends({job_root})
        job_lvl2_a = Job(self.method)
        job_lvl2_a.add_depends({job_lvl1_a})

        job_2_root = Job(self.method)
        job_2_child = Job(self.method)
        job_2_child.add_depends({job_2_root})

        # Jobs must be stored after the dependencies are set up.
        # (Or if not, a new store must be called on the parent)
        job_root.store()
        job_lvl1_a.store()
        job_lvl1_b.store()
        job_lvl2_a.store()

        job_2_root.store()
        job_2_child.store()

        record_root = job_root.db_record()
        record_lvl1_a = job_lvl1_a.db_record()
        record_lvl1_b = job_lvl1_b.db_record()
        record_lvl2_a = job_lvl2_a.db_record()

        record_2_root = job_2_root.db_record()
        record_2_child = job_2_child.db_record()

        expected_nodes = sorted(
            [record_root.id, record_lvl1_a.id,
             record_lvl1_b.id, record_lvl2_a.id]
        )
        expected_edges = sorted(
            [
                (record_root.id, record_lvl1_a.id),
                (record_lvl1_a.id, record_lvl2_a.id),
                (record_root.id, record_lvl1_b.id),
            ]
        )

        records = [record_root, record_lvl1_a, record_lvl1_b, record_lvl2_a]
        for record in records:
            self.assertEqual(
                sorted(record.dependency_graph['nodes']),
                expected_nodes
            )
            self.assertEqual(
                sorted(record.dependency_graph['edges']),
                expected_edges
            )

        expected_nodes = sorted([record_2_root.id, record_2_child.id])
        expected_edges = sorted([(record_2_root.id, record_2_child.id)])

        for record in [record_2_root, record_2_child]:
            self.assertEqual(
                sorted(record.dependency_graph['nodes']),
                expected_nodes
            )
            self.assertEqual(
                sorted(record.dependency_graph['edges']),
                expected_edges
            )

    def test_no_dependency_graph_single_job(self):
        job_root = Job(self.method)
        job_root.store()
        self.assertEqual(job_root.db_record().dependency_graph, {})

    def test_depends_graph_uuid(self):
        """All jobs with dependencies share the same graph uuid"""
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

        jobs = [job_root, job_lvl1_a, job_lvl1_b, job_lvl2_a]
        self.assertTrue(job_root.graph_uuid)
        self.assertEqual(len(set(j.graph_uuid for j in jobs)), 1)
        self.assertEqual(job_root.graph_uuid, job_root.db_record().graph_uuid)
        self.assertEqual(job_lvl1_a.graph_uuid,
                         job_lvl1_a.db_record().graph_uuid)
        self.assertEqual(job_lvl1_b.graph_uuid,
                         job_lvl1_b.db_record().graph_uuid)
        self.assertEqual(job_lvl2_a.graph_uuid,
                         job_lvl2_a.db_record().graph_uuid)
