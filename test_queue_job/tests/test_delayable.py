# copyright 2019 Camptocamp
# Copyright 2019 Guewen Baconnier
# license agpl-3.0 or later (http://www.gnu.org/licenses/agpl.html)


import odoo.tests.common as common

from odoo.addons.queue_job.delay import (
    Delayable,
    DelayableGroup,
    DelayableChain,
    chain,
    group,
)


class TestDelayable(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.queue_job = self.env['queue.job']
        self.test_model = self.env['test.queue.job']
        self.method = self.env['test.queue.job'].testing_method
        self.node = Delayable(self.test_model).testing_method(1)
        self.node2 = Delayable(self.test_model).testing_method(2)
        self.node3 = Delayable(self.test_model).testing_method(3)
        self.node4 = Delayable(self.test_model).testing_method(4)
        self.node5 = Delayable(self.test_model).testing_method(5)
        self.node6 = Delayable(self.test_model).testing_method(6)
        self.node7 = Delayable(self.test_model).testing_method(7)
        self.node8 = Delayable(self.test_model).testing_method(8)

    def test_delayable_delay_single(self):
        self.node.delay()
        self.assert_generated_job(self.node)

    def assert_generated_job(self, *nodes):
        for node in nodes:
            self.assertTrue(node._generated_job)
            job = node._generated_job
            self.assertTrue(job.db_record().id)

    def assert_depends_on(self, delayable, parent_delayables):
        self.assertEqual(
            delayable._generated_job._depends_on,
            {parent._generated_job for parent in parent_delayables}
        )

    def assert_reverse_depends_on(self, delayable, child_delayables):
        self.assertEqual(
            set(delayable._generated_job._reverse_depends_on),
            {child._generated_job for child in child_delayables}
        )

    def assert_dependencies(self, nodes):
        reverse_dependencies = {}
        for child, parents in nodes.items():
            self.assert_depends_on(child, parents)
            for parent in parents:
                reverse_dependencies.setdefault(parent, set()).add(child)
        for parent, children in reverse_dependencies.items():
            self.assert_reverse_depends_on(parent, children)

    def test_delayable_delay_done(self):
        self.node.done(self.node2).delay()
        self.assert_generated_job(self.node, self.node2)
        self.assert_dependencies({self.node: {}, self.node2: {self.node}})

    def test_delayable_delay_done_multi(self):
        self.node.done(self.node2, self.node3).delay()
        self.assert_generated_job(self.node, self.node2, self.node3)
        self.assert_dependencies({
            self.node: {}, self.node2: {self.node}, self.node3: {self.node}
        })

    def test_delayable_delay_group(self):
        DelayableGroup(self.node, self.node2, self.node3).delay()
        self.assert_generated_job(self.node, self.node2, self.node3)
        self.assert_dependencies(
            {self.node: {}, self.node2: {}, self.node3: {}}
        )

    def test_group_function(self):
        group(self.node, self.node2, self.node3).delay()
        self.assert_generated_job(self.node, self.node2, self.node3)
        self.assert_dependencies(
            {self.node: {}, self.node2: {}, self.node3: {}}
        )

    def test_delayable_delay_job_after_group(self):
        DelayableGroup(self.node, self.node2).done(self.node3).delay()
        self.assert_generated_job(self.node, self.node2, self.node3)
        self.assert_dependencies({
            self.node: {}, self.node2: {}, self.node3: {self.node, self.node2}
        })

    def test_delayable_delay_group_after_group(self):
        g1 = DelayableGroup(self.node, self.node2)
        g2 = DelayableGroup(self.node3, self.node4)
        g1.done(g2).delay()
        self.assert_generated_job(
            self.node, self.node2, self.node3, self.node4
        )
        self.assert_dependencies({
            self.node: {}, self.node2: {},
            self.node3: {self.node, self.node2},
            self.node4: {self.node, self.node2},
        })

    def test_delayable_delay_implicit_group_after_group(self):
        g1 = DelayableGroup(self.node, self.node2).done(self.node3, self.node4)
        g1.delay()
        self.assert_generated_job(
            self.node, self.node2, self.node3, self.node4
        )
        self.assert_dependencies({
            self.node: {}, self.node2: {},
            self.node3: {self.node, self.node2},
            self.node4: {self.node, self.node2},
        })

    def test_delayable_delay_group_after_group_after_group(self):
        g1 = DelayableGroup(self.node)
        g2 = DelayableGroup(self.node2)
        g3 = DelayableGroup(self.node3)
        g4 = DelayableGroup(self.node4)
        g1.done(g2.done(g3.done(g4))).delay()
        self.assert_generated_job(
            self.node, self.node2, self.node3, self.node4
        )
        self.assert_dependencies({
            self.node: {},
            self.node2: {self.node},
            self.node3: {self.node2},
            self.node4: {self.node3},
        })

    def test_delayable_diamond(self):
        g1 = DelayableGroup(self.node2, self.node3)
        g1.done(self.node4)
        self.node.done(g1)
        self.node.delay()
        self.assert_generated_job(
            self.node, self.node2, self.node3, self.node4
        )
        self.assert_dependencies({
            self.node: {},
            self.node2: {self.node},
            self.node3: {self.node},
            self.node4: {self.node2, self.node3},
        })

    def test_delayable_chain(self):
        c1 = DelayableChain(self.node, self.node2, self.node3)
        c1.delay()
        self.assert_generated_job(
            self.node, self.node2, self.node3
        )
        self.assert_dependencies({
            self.node: {},
            self.node2: {self.node},
            self.node3: {self.node2},
        })

    def test_chain_function(self):
        c1 = chain(self.node, self.node2, self.node3)
        c1.delay()
        self.assert_generated_job(
            self.node, self.node2, self.node3
        )
        self.assert_dependencies({
            self.node: {},
            self.node2: {self.node},
            self.node3: {self.node2},
        })

    def test_delayable_chain_after_job(self):
        c1 = DelayableChain(self.node2, self.node3, self.node4)
        self.node.done(c1)
        self.node.delay()
        self.assert_generated_job(
            self.node, self.node2, self.node3, self.node4
        )
        self.assert_dependencies({
            self.node: {},
            self.node2: {self.node},
            self.node3: {self.node2},
            self.node4: {self.node3},
        })

    def test_delayable_chain_after_chain(self):
        chain1 = DelayableChain(self.node, self.node2, self.node3)
        chain2 = DelayableChain(self.node4, self.node5, self.node6)
        chain1.done(chain2)
        chain1.delay()
        self.assert_generated_job(
            self.node, self.node2, self.node3,
            self.node4, self.node5, self.node6,
        )
        self.assert_dependencies({
            self.node: {},
            self.node2: {self.node},
            self.node3: {self.node2},
            self.node4: {self.node3},
            self.node5: {self.node4},
            self.node6: {self.node5},
        })

    def test_delayable_group_of_chain(self):
        chain1 = DelayableChain(self.node, self.node2)
        chain2 = DelayableChain(self.node3, self.node4)
        chain3 = DelayableChain(self.node5, self.node6)
        chain4 = DelayableChain(self.node7, self.node8)
        g1 = DelayableGroup(chain1, chain2).done(chain3, chain4)
        g1.delay()
        self.assert_generated_job(
            self.node, self.node2, self.node3, self.node4,
            self.node5, self.node6, self.node7, self.node8,
        )
        self.assert_dependencies({
            self.node: {},
            self.node3: {},
            self.node2: {self.node},
            self.node4: {self.node3},
            self.node5: {self.node4, self.node2},
            self.node7: {self.node4, self.node2},
            self.node6: {self.node5},
            self.node8: {self.node7},
        })

    def test_log_not_delayed(self):
        logger_name = 'odoo.addons.queue_job'
        with self.assertLogs(logger_name, level='WARN') as test:
            # When a Delayable never gets a delay() call,
            # when the GC collects it and calls __del__, a warning
            # will be displayed. We cannot test this is a scenario
            # using the GC as it isn't predictable. Call __del__
            # directly
            self.node.__del__()
            expected = (
                'WARNING:odoo.addons.queue_job.delay:Delayable '
                'Delayable(test.queue.job().testing_method((1,), {}))'
                ' was prepared but never delayed'
            )
            self.assertEqual(test.output, [expected])

    def test_delay_job_already_exists(self):
        self.node2.delay()
        self.node.done(self.node2).delay()
        self.assert_generated_job(self.node, self.node2)
        self.assert_dependencies({self.node: {}, self.node2: {self.node}})
