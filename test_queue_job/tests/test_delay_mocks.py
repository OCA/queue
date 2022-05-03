# Copyright 2021 Guewen Baconnier
# license lgpl-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import os

from unittest import mock

import odoo.tests.common as common

from odoo.addons.queue_job.delay import Delayable
from odoo.addons.queue_job.job import identity_exact
from odoo.addons.queue_job.tests.common import mock_with_delay, trap_jobs

from odoo.tools import mute_logger


class TestDelayMocks(common.SavepointCase):

    def test_trap_jobs_on_with_delay(self):
        with trap_jobs() as trap:
            self.env['test.queue.job'].button_that_uses_with_delay()
            trap.assert_jobs_count(1)
            trap.assert_jobs_count(
                1, only=self.env['test.queue.job'].testing_method
            )

            trap.assert_enqueued_job(
                self.env['test.queue.job'].testing_method,
                args=(1,),
                kwargs={"foo": 2},
                properties=dict(
                    channel="root.test",
                    description="Test",
                    eta=15,
                    identity_key=identity_exact,
                    max_retries=1,
                    priority=15,
                )
            )

    def test_trap_jobs_on_graph(self):
        with trap_jobs() as trap:
            self.env['test.queue.job'].button_that_uses_delayable_chain()
            trap.assert_jobs_count(3)
            trap.assert_jobs_count(
                2, only=self.env['test.queue.job'].testing_method
            )
            trap.assert_jobs_count(
                1, only=self.env['test.queue.job'].no_description
            )

            trap.assert_enqueued_job(
                self.env['test.queue.job'].testing_method,
                args=(1,),
                kwargs={"foo": 2},
                properties=dict(
                    channel="root.test",
                    description="Test",
                    eta=15,
                    identity_key=identity_exact,
                    max_retries=1,
                    priority=15,
                )
            )
            trap.assert_enqueued_job(
                self.env['test.queue.job'].testing_method,
                args=("x",),
                kwargs={"foo": "y"},
            )
            trap.assert_enqueued_job(
                self.env['test.queue.job'].no_description,
            )

            trap.perform_enqueued_jobs()

    def test_trap_jobs_perform(self):
        with trap_jobs() as trap:
            model = self.env["test.queue.job"]
            model.with_delay(priority=1).create_ir_logging(
                "test_trap_jobs_perform single"
            )
            node = Delayable(model).create_ir_logging(
                "test_trap_jobs_perform graph 1"
            )
            node2 = Delayable(model).create_ir_logging(
                "test_trap_jobs_perform graph 2"
            )
            node3 = Delayable(model).create_ir_logging(
                "test_trap_jobs_perform graph 3"
            )
            node2.on_done(node3)
            node3.on_done(node)
            node2.delay()

            # jobs are not executed
            logs = self.env["ir.logging"].search(
                [
                    ("name", "=", "test_queue_job"),
                    ("func", "=", "create_ir_logging"),
                ],
                order="id asc",
            )
            self.assertEqual(len(logs), 0)

            trap.assert_jobs_count(4)

            # perform the jobs
            trap.perform_enqueued_jobs()

            logs = self.env["ir.logging"].search(
                [
                    ("name", "=", "test_queue_job"),
                    ("func", "=", "create_ir_logging"),
                ],
                order="id asc",
            )
            self.assertEqual(len(logs), 4)

            # check if they are executed in order
            self.assertEqual(logs[0].message, "test_trap_jobs_perform single")
            self.assertEqual(logs[1].message, "test_trap_jobs_perform graph 2")
            self.assertEqual(logs[2].message, "test_trap_jobs_perform graph 3")
            self.assertEqual(logs[3].message, "test_trap_jobs_perform graph 1")

    def test_mock_with_delay(self):
        with mock_with_delay() as (delayable_cls, delayable):
            self.env['test.queue.job'].button_that_uses_with_delay()

            self.assertEqual(delayable_cls.call_count, 1)
            # arguments passed in 'with_delay()'
            delay_args, delay_kwargs = delayable_cls.call_args
            self.assertEqual(
                delay_args, (self.env["test.queue.job"],)
            )
            self.assertDictEqual(delay_kwargs, {
                "channel": "root.test",
                "description": "Test",
                "eta": 15,
                "identity_key": identity_exact,
                "max_retries": 1,
                "priority": 15,
            })

            # check what's passed to the job method 'testing_method'
            self.assertEqual(delayable.testing_method.call_count, 1)
            delay_args, delay_kwargs = delayable.testing_method.call_args
            self.assertEqual(delay_args, (1,))
            self.assertDictEqual(delay_kwargs, {"foo": 2})

    @mute_logger('odoo.addons.queue_job.models.base')
    @mock.patch.dict(os.environ, {"TEST_QUEUE_JOB_NO_DELAY": "1"})
    def test_delay_graph_direct_exec_env_var(self):
        node = Delayable(self.env["test.queue.job"]).create_ir_logging(
            "test_delay_graph_direct_exec 1"
        )
        node2 = Delayable(self.env["test.queue.job"]).create_ir_logging(
            "test_delay_graph_direct_exec 2"
        )
        node2.on_done(node)
        node2.delay()
        # jobs are executed directly
        logs = self.env["ir.logging"].search(
            [
                ("name", "=", "test_queue_job"),
                ("func", "=", "create_ir_logging"),
            ],
            order="id asc",
        )
        self.assertEqual(len(logs), 2)
        # check if they are executed in order
        self.assertEqual(logs[0].message, "test_delay_graph_direct_exec 2")
        self.assertEqual(logs[1].message, "test_delay_graph_direct_exec 1")

    @mute_logger('odoo.addons.queue_job.models.base')
    def test_delay_graph_direct_exec_context_key(self):
        node = Delayable(
            self.env["test.queue.job"].with_context(
                test_queue_job_no_delay=True
            )
        ).create_ir_logging(
            "test_delay_graph_direct_exec 1"
        )
        node2 = Delayable(self.env["test.queue.job"]).create_ir_logging(
            "test_delay_graph_direct_exec 2"
        )
        node2.on_done(node)
        node2.delay()
        # jobs are executed directly
        logs = self.env["ir.logging"].search(
            [
                ("name", "=", "test_queue_job"),
                ("func", "=", "create_ir_logging"),
            ],
            order="id asc",
        )
        self.assertEqual(len(logs), 2)
        # check if they are executed in order
        self.assertEqual(logs[0].message, "test_delay_graph_direct_exec 2")
        self.assertEqual(logs[1].message, "test_delay_graph_direct_exec 1")

    @mute_logger('odoo.addons.queue_job.models.base')
    @mock.patch.dict(os.environ, {"TEST_QUEUE_JOB_NO_DELAY": "1"})
    def test_delay_with_delay_direct_exec_env_var(self):
        model = self.env["test.queue.job"]
        model.with_delay().create_ir_logging("test_delay_graph_direct_exec 1")
        # jobs are executed directly
        logs = self.env["ir.logging"].search(
            [
                ("name", "=", "test_queue_job"),
                ("func", "=", "create_ir_logging"),
            ],
            order="id asc",
        )
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].message, "test_delay_graph_direct_exec 1")

    @mute_logger('odoo.addons.queue_job.models.base')
    def test_delay_with_delay_direct_exec_context_key(self):
        model = self.env["test.queue.job"].with_context(
            test_queue_job_no_delay=True
        )
        model.with_delay().create_ir_logging("test_delay_graph_direct_exec 1")
        # jobs are executed directly
        logs = self.env["ir.logging"].search(
            [
                ("name", "=", "test_queue_job"),
                ("func", "=", "create_ir_logging"),
            ],
            order="id asc",
        )
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].message, "test_delay_graph_direct_exec 1")
