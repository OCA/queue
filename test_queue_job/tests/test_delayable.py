# copyright 2019 Camptocamp
# Copyright 2019 Guewen Baconnier
# license lgpl-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import odoo.tests.common as common

from odoo.addons.queue_job.delay import (
    Delayable,
    DelayableChain,
    DelayableGroup,
    chain,
    group,
)


class TestDelayable(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.queue_job = cls.env["queue.job"]
        cls.test_model = cls.env["test.queue.job"]
        cls.method = cls.env["test.queue.job"].testing_method

    def job_node(self, id_):
        return Delayable(self.test_model).testing_method(id_)

    def assert_generated_job(self, *nodes):
        for node in nodes:
            self.assertTrue(node._generated_job)
            job = node._generated_job
            self.assertTrue(job.db_record().id)

    def assert_depends_on(self, delayable, parent_delayables):
        self.assertEqual(
            delayable._generated_job._depends_on,
            {parent._generated_job for parent in parent_delayables},
        )

    def assert_reverse_depends_on(self, delayable, child_delayables):
        self.assertEqual(
            set(delayable._generated_job._reverse_depends_on),
            {child._generated_job for child in child_delayables},
        )

    def assert_dependencies(self, nodes):
        reverse_dependencies = {}
        for child, parents in nodes.items():
            self.assert_depends_on(child, parents)
            for parent in parents:
                reverse_dependencies.setdefault(parent, set()).add(child)
        for parent, children in reverse_dependencies.items():
            self.assert_reverse_depends_on(parent, children)

    def test_delayable_delay_single(self):
        node = self.job_node(1)
        node.delay()
        self.assert_generated_job(node)

    def test_delayable_delay_on_done(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node.on_done(node2).delay()
        self.assert_generated_job(node, node2)
        self.assert_dependencies({node: {}, node2: {node}})

    def test_delayable_delay_done_multi(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        node.on_done(node2, node3).delay()
        self.assert_generated_job(node, node2, node3)
        self.assert_dependencies({node: {}, node2: {node}, node3: {node}})

    def test_delayable_delay_group(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        DelayableGroup(node, node2, node3).delay()
        self.assert_generated_job(node, node2, node3)
        self.assert_dependencies({node: {}, node2: {}, node3: {}})

    def test_group_function(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        group(node, node2, node3).delay()
        self.assert_generated_job(node, node2, node3)
        self.assert_dependencies({node: {}, node2: {}, node3: {}})

    def test_delayable_delay_job_after_group(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        DelayableGroup(node, node2).on_done(node3).delay()
        self.assert_generated_job(node, node2, node3)
        self.assert_dependencies({node: {}, node2: {}, node3: {node, node2}})

    def test_delayable_delay_group_after_group(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        node4 = self.job_node(4)
        g1 = DelayableGroup(node, node2)
        g2 = DelayableGroup(node3, node4)
        g1.on_done(g2).delay()
        self.assert_generated_job(node, node2, node3, node4)
        self.assert_dependencies(
            {
                node: {},
                node2: {},
                node3: {node, node2},
                node4: {node, node2},
            }
        )

    def test_delayable_delay_implicit_group_after_group(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        node4 = self.job_node(4)
        g1 = DelayableGroup(node, node2).on_done(node3, node4)
        g1.delay()
        self.assert_generated_job(node, node2, node3, node4)
        self.assert_dependencies(
            {
                node: {},
                node2: {},
                node3: {node, node2},
                node4: {node, node2},
            }
        )

    def test_delayable_delay_group_after_group_after_group(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        node4 = self.job_node(4)
        g1 = DelayableGroup(node)
        g2 = DelayableGroup(node2)
        g3 = DelayableGroup(node3)
        g4 = DelayableGroup(node4)
        g1.on_done(g2.on_done(g3.on_done(g4))).delay()
        self.assert_generated_job(node, node2, node3, node4)
        self.assert_dependencies(
            {
                node: {},
                node2: {node},
                node3: {node2},
                node4: {node3},
            }
        )

    def test_delayable_diamond(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        node4 = self.job_node(4)
        g1 = DelayableGroup(node2, node3)
        g1.on_done(node4)
        node.on_done(g1)
        node.delay()
        self.assert_generated_job(node, node2, node3, node4)
        self.assert_dependencies(
            {
                node: {},
                node2: {node},
                node3: {node},
                node4: {node2, node3},
            }
        )

    def test_delayable_chain(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        c1 = DelayableChain(node, node2, node3)
        c1.delay()
        self.assert_generated_job(node, node2, node3)
        self.assert_dependencies(
            {
                node: {},
                node2: {node},
                node3: {node2},
            }
        )

    def test_chain_function(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        c1 = chain(node, node2, node3)
        c1.delay()
        self.assert_generated_job(node, node2, node3)
        self.assert_dependencies(
            {
                node: {},
                node2: {node},
                node3: {node2},
            }
        )

    def test_delayable_chain_after_job(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        node4 = self.job_node(4)
        c1 = DelayableChain(node2, node3, node4)
        node.on_done(c1)
        node.delay()
        self.assert_generated_job(node, node2, node3, node4)
        self.assert_dependencies(
            {
                node: {},
                node2: {node},
                node3: {node2},
                node4: {node3},
            }
        )

    def test_delayable_chain_after_chain(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        node4 = self.job_node(4)
        node5 = self.job_node(5)
        node6 = self.job_node(6)
        chain1 = DelayableChain(node, node2, node3)
        chain2 = DelayableChain(node4, node5, node6)
        chain1.on_done(chain2)
        chain1.delay()
        self.assert_generated_job(node, node2, node3, node4, node5, node6)
        self.assert_dependencies(
            {
                node: {},
                node2: {node},
                node3: {node2},
                node4: {node3},
                node5: {node4},
                node6: {node5},
            }
        )

    def test_delayable_group_of_chain(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node3 = self.job_node(3)
        node4 = self.job_node(4)
        node5 = self.job_node(5)
        node6 = self.job_node(6)
        node7 = self.job_node(7)
        node8 = self.job_node(8)
        chain1 = DelayableChain(node, node2)
        chain2 = DelayableChain(node3, node4)
        chain3 = DelayableChain(node5, node6)
        chain4 = DelayableChain(node7, node8)
        g1 = DelayableGroup(chain1, chain2).on_done(chain3, chain4)
        g1.delay()
        self.assert_generated_job(
            node,
            node2,
            node3,
            node4,
            node5,
            node6,
            node7,
            node8,
        )
        self.assert_dependencies(
            {
                node: {},
                node3: {},
                node2: {node},
                node4: {node3},
                node5: {node4, node2},
                node7: {node4, node2},
                node6: {node5},
                node8: {node7},
            }
        )

    def test_log_not_delayed(self):
        logger_name = "odoo.addons.queue_job"
        with self.assertLogs(logger_name, level="WARN") as test:
            # When a Delayable never gets a delay() call,
            # when the GC collects it and calls __del__, a warning
            # will be displayed. We cannot test this is a scenario
            # using the GC as it isn't predictable. Call __del__
            # directly
            node = self.job_node(1)
            node.__del__()
            expected = (
                "WARNING:odoo.addons.queue_job.delay:Delayable "
                "Delayable(test.queue.job().testing_method((1,), {}))"
                " was prepared but never delayed"
            )
            self.assertEqual(test.output, [expected])

    def test_delay_job_already_exists(self):
        node = self.job_node(1)
        node2 = self.job_node(2)
        node2.delay()
        node.on_done(node2).delay()
        self.assert_generated_job(node, node2)
        self.assert_dependencies({node: {}, node2: {node}})
