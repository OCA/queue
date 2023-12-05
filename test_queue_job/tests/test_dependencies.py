# Copyright 2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import odoo.tests.common as common

from odoo.addons.queue_job.delay import DelayableGraph, chain, group
from odoo.addons.queue_job.job import PENDING, WAIT_DEPENDENCIES, Job


class TestJobDependencies(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.queue_job = cls.env["queue.job"]
        cls.method = cls.env["test.queue.job"].testing_method

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
        self.assertEqual(job_root.db_record().dependencies["depends_on"], [])
        self.assertEqual(
            sorted(job_root.db_record().dependencies["reverse_depends_on"]),
            sorted([job_lvl1_a.uuid, job_lvl1_b.uuid]),
        )

        self.assertEqual(
            job_lvl1_a.db_record().dependencies["depends_on"], [job_root.uuid]
        )
        self.assertEqual(
            job_lvl1_a.db_record().dependencies["reverse_depends_on"], [job_lvl2_a.uuid]
        )

        self.assertEqual(
            job_lvl1_b.db_record().dependencies["depends_on"], [job_root.uuid]
        )
        self.assertEqual(job_lvl1_b.db_record().dependencies["reverse_depends_on"], [])

        self.assertEqual(
            job_lvl2_a.db_record().dependencies["depends_on"], [job_lvl1_a.uuid]
        )
        self.assertEqual(job_lvl2_a.db_record().dependencies["reverse_depends_on"], [])

    def test_depends_store_after(self):
        job_root = Job(self.method)
        job_root.store()
        job_a = Job(self.method)
        job_a.add_depends({job_root})
        job_a.store()

        # as the reverse dependency has been added after the root job has been
        # stored, it is not reflected in DB
        self.assertEqual(job_root.db_record().dependencies["reverse_depends_on"], [])

        # a new store will write it
        job_root.store()
        self.assertEqual(
            job_root.db_record().dependencies["reverse_depends_on"], [job_a.uuid]
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

        DelayableGraph._ensure_same_graph_uuid([job_root, job_a])

        job_root.store()
        job_a.store()

        self.assertEqual(job_a.state, WAIT_DEPENDENCIES)

        # these are the steps run by RunJobController
        job_root.perform()
        job_root.set_done()
        job_root.store()
        self.env.flush_all()

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

        DelayableGraph._ensure_same_graph_uuid(
            [
                job_root,
                job_lvl1_a,
                job_lvl1_b,
                job_lvl2_a,
            ]
        )

        job_2_root = Job(self.method)
        job_2_child = Job(self.method)
        job_2_child.add_depends({job_2_root})

        DelayableGraph._ensure_same_graph_uuid([job_2_root, job_2_child])

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

        expected_nodes = [
            {
                "id": record_root.id,
                "title": "<strong>Method used for tests</strong><br/>"
                "test.queue.job().testing_method()",
                "color": "#D2E5FF",
                "border": "#2B7CE9",
                "shadow": True,
            },
            {
                "id": record_lvl1_a.id,
                "title": "<strong>Method used for tests</strong><br/>"
                "test.queue.job().testing_method()",
                "color": "#D2E5FF",
                "border": "#2B7CE9",
                "shadow": True,
            },
            {
                "id": record_lvl1_b.id,
                "title": "<strong>Method used for tests</strong><br/>"
                "test.queue.job().testing_method()",
                "color": "#D2E5FF",
                "border": "#2B7CE9",
                "shadow": True,
            },
            {
                "id": record_lvl2_a.id,
                "title": "<strong>Method used for tests</strong><br/>"
                "test.queue.job().testing_method()",
                "color": "#D2E5FF",
                "border": "#2B7CE9",
                "shadow": True,
            },
        ]
        expected_edges = sorted(
            [
                [record_root.id, record_lvl1_a.id],
                [record_lvl1_a.id, record_lvl2_a.id],
                [record_root.id, record_lvl1_b.id],
            ]
        )

        records = [record_root, record_lvl1_a, record_lvl1_b, record_lvl2_a]

        for record in records:
            self.assertEqual(
                sorted(record.dependency_graph["nodes"], key=lambda d: d["id"]),
                expected_nodes,
            )
            self.assertEqual(sorted(record.dependency_graph["edges"]), expected_edges)

        expected_nodes = [
            {
                "id": record_2_root.id,
                "title": "<strong>Method used for tests</strong><br/>"
                "test.queue.job().testing_method()",
                "color": "#D2E5FF",
                "border": "#2B7CE9",
                "shadow": True,
            },
            {
                "id": record_2_child.id,
                "title": "<strong>Method used for tests</strong><br/>"
                "test.queue.job().testing_method()",
                "color": "#D2E5FF",
                "border": "#2B7CE9",
                "shadow": True,
            },
        ]
        expected_edges = sorted([[record_2_root.id, record_2_child.id]])

        for record in [record_2_root, record_2_child]:
            self.assertEqual(
                sorted(record.dependency_graph["nodes"], key=lambda d: d["id"]),
                expected_nodes,
            )
            self.assertEqual(sorted(record.dependency_graph["edges"]), expected_edges)

    def test_no_dependency_graph_single_job(self):
        """A single job has no graph"""
        job = self.env["test.queue.job"].with_delay().testing_method()
        self.assertEqual(job.db_record().dependency_graph, {})
        self.assertIsNone(job.graph_uuid)

    def test_depends_graph_uuid(self):
        """All jobs in a graph share the same graph uuid"""
        model = self.env["test.queue.job"]
        delayable1 = model.delayable().testing_method(1)
        delayable2 = model.delayable().testing_method(2)
        delayable3 = model.delayable().testing_method(3)
        delayable4 = model.delayable().testing_method(4)
        group1 = group(delayable1, delayable2)
        group2 = group(delayable3, delayable4)
        chain_root = chain(group1, group2)
        chain_root.delay()

        jobs = [
            delayable._generated_job
            for delayable in [delayable1, delayable2, delayable3, delayable4]
        ]

        self.assertTrue(jobs[0].graph_uuid)
        self.assertEqual(len({j.graph_uuid for j in jobs}), 1)
        for job in jobs:
            self.assertEqual(job.graph_uuid, job.db_record().graph_uuid)

    def test_depends_graph_uuid_group(self):
        """All jobs in a group share the same graph uuid"""
        g = group(
            self.env["test.queue.job"].delayable().testing_method(),
            self.env["test.queue.job"].delayable().testing_method(),
        )
        g.delay()

        jobs = [delayable._generated_job for delayable in g._delayables]

        self.assertTrue(jobs[0].graph_uuid)
        self.assertTrue(jobs[1].graph_uuid)
        self.assertEqual(jobs[0].graph_uuid, jobs[1].graph_uuid)
