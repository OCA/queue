# Copyright 2021 Guewen Baconnier
# license lgpl-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import os
from unittest import mock

import odoo.tests.common as common
from odoo.tools import mute_logger

from odoo.addons.queue_job.delay import Delayable
from odoo.addons.queue_job.job import identity_exact
from odoo.addons.queue_job.tests.common import mock_with_delay, trap_jobs


class TestDelayMocks(common.TransactionCase):
    def test_trap_jobs_on_with_delay_model(self):
        with trap_jobs() as trap:
            self.env["test.queue.job"].button_that_uses_with_delay()
            trap.assert_jobs_count(1)
            trap.assert_jobs_count(1, only=self.env["test.queue.job"].testing_method)

            trap.assert_enqueued_job(
                self.env["test.queue.job"].testing_method,
                args=(1,),
                kwargs={"foo": 2},
                properties=dict(
                    channel="root.test",
                    description="Test",
                    eta=15,
                    identity_key=identity_exact,
                    max_retries=1,
                    priority=15,
                ),
            )

    def test_trap_jobs_on_with_delay_recordset(self):
        recordset = self.env["test.queue.job"].create({"name": "test"})
        with trap_jobs() as trap:
            recordset.button_that_uses_with_delay()
            trap.assert_jobs_count(1)
            trap.assert_jobs_count(1, only=recordset.testing_method)

            trap.assert_enqueued_job(
                recordset.testing_method,
                args=(1,),
                kwargs={"foo": 2},
                properties=dict(
                    channel="root.test",
                    description="Test",
                    eta=15,
                    identity_key=identity_exact,
                    max_retries=1,
                    priority=15,
                ),
            )

    def test_trap_jobs_on_with_delay_recordset_no_properties(self):
        """Verify that trap_jobs() can omit properties"""
        recordset = self.env["test.queue.job"].create({"name": "test"})
        with trap_jobs() as trap:
            recordset.button_that_uses_with_delay()

            trap.assert_enqueued_job(
                recordset.testing_method,
                args=(1,),
                kwargs={"foo": 2},
            )

    def test_trap_jobs_on_with_delay_recordset_partial_properties(self):
        """Verify that trap_jobs() can check partially properties"""
        recordset = self.env["test.queue.job"].create({"name": "test"})
        with trap_jobs() as trap:
            recordset.button_that_uses_with_delay()

            trap.assert_enqueued_job(
                recordset.testing_method,
                args=(1,),
                kwargs={"foo": 2},
                properties=dict(
                    description="Test",
                    eta=15,
                ),
            )

    def test_trap_with_identity_key(self):
        with trap_jobs() as trap:
            self.env["test.queue.job"].button_that_uses_with_delay()
            trap.assert_jobs_count(1)
            trap.assert_jobs_count(1, only=self.env["test.queue.job"].testing_method)

            trap.assert_enqueued_job(
                self.env["test.queue.job"].testing_method,
                args=(1,),
                kwargs={"foo": 2},
                properties=dict(
                    channel="root.test",
                    description="Test",
                    eta=15,
                    identity_key=identity_exact,
                    max_retries=1,
                    priority=15,
                ),
            )

            # Should not enqueue again
            self.env["test.queue.job"].button_that_uses_with_delay()
            trap.assert_jobs_count(1)

            trap.perform_enqueued_jobs()
            # Should no longer be enqueued
            trap.assert_jobs_count(0)

            # Can now requeue
            self.env["test.queue.job"].button_that_uses_with_delay()
            trap.assert_jobs_count(1)

    def test_trap_jobs_on_with_delay_assert_model_count_mismatch(self):
        recordset = self.env["test.queue.job"].create({"name": "test"})
        with trap_jobs() as trap:
            self.env["test.queue.job"].button_that_uses_with_delay()
            trap.assert_jobs_count(1)
            with self.assertRaises(AssertionError, msg="0 != 1"):
                trap.assert_jobs_count(1, only=recordset.testing_method)

    def test_trap_jobs_on_with_delay_assert_recordset_count_mismatch(self):
        recordset = self.env["test.queue.job"].create({"name": "test"})
        with trap_jobs() as trap:
            recordset.button_that_uses_with_delay()
            trap.assert_jobs_count(1)
            with self.assertRaises(AssertionError, msg="0 != 1"):
                trap.assert_jobs_count(
                    1, only=self.env["test.queue.job"].testing_method
                )

    def test_trap_jobs_on_with_delay_assert_model_enqueued_mismatch(self):
        recordset = self.env["test.queue.job"].create({"name": "test"})
        with trap_jobs() as trap:
            recordset.button_that_uses_with_delay()
            trap.assert_jobs_count(1)
            message = (
                r"Job <test\.queue.job\(\)>\.testing_method\(1, foo=2\) with "
                r"properties \(channel=root\.test, description=Test, eta=15, "
                "identity_key=<function identity_exact at 0x[0-9a-fA-F]+>, "
                "max_retries=1, priority=15\\) was not enqueued\\.\n"
                "Actual enqueued jobs:\n"
                r" \* <test.queue.job\(%s,\)>.testing_method\(1, foo=2\) with properties "
                r"\(priority=15, max_retries=1, eta=15, description=Test, channel=root.test, "
                r"identity_key=<function identity_exact at 0x[0-9a-fA-F]+>\)"
            ) % (recordset.id,)
            with self.assertRaisesRegex(AssertionError, message):
                trap.assert_enqueued_job(
                    self.env["test.queue.job"].testing_method,
                    args=(1,),
                    kwargs={"foo": 2},
                    properties=dict(
                        channel="root.test",
                        description="Test",
                        eta=15,
                        identity_key=identity_exact,
                        max_retries=1,
                        priority=15,
                    ),
                )

    def test_trap_jobs_on_with_delay_assert_recordset_enqueued_mismatch(self):
        recordset = self.env["test.queue.job"].create({"name": "test"})
        with trap_jobs() as trap:
            self.env["test.queue.job"].button_that_uses_with_delay()
            trap.assert_jobs_count(1)
            message = (
                r"Job <test\.queue.job\(%s,\)>\.testing_method\(1, foo=2\) with "
                r"properties \(channel=root\.test, description=Test, eta=15, "
                "identity_key=<function identity_exact at 0x[0-9a-fA-F]+>, "
                "max_retries=1, priority=15\\) was not enqueued\\.\n"
                "Actual enqueued jobs:\n"
                r" \* <test.queue.job\(\)>.testing_method\(1, foo=2\) with properties "
                r"\(priority=15, max_retries=1, eta=15, description=Test, channel=root.test, "
                r"identity_key=<function identity_exact at 0x[0-9a-fA-F]+>\)"
            ) % (recordset.id,)
            with self.assertRaisesRegex(AssertionError, message):
                trap.assert_enqueued_job(
                    recordset.testing_method,
                    args=(1,),
                    kwargs={"foo": 2},
                    properties=dict(
                        channel="root.test",
                        description="Test",
                        eta=15,
                        identity_key=identity_exact,
                        max_retries=1,
                        priority=15,
                    ),
                )

    def test_trap_jobs_on_graph(self):
        with trap_jobs() as trap:
            self.env["test.queue.job"].button_that_uses_delayable_chain()
            trap.assert_jobs_count(3)
            trap.assert_jobs_count(2, only=self.env["test.queue.job"].testing_method)
            trap.assert_jobs_count(1, only=self.env["test.queue.job"].no_description)

            trap.assert_enqueued_job(
                self.env["test.queue.job"].testing_method,
                args=(1,),
                kwargs={"foo": 2},
                properties=dict(
                    channel="root.test",
                    description="Test",
                    eta=15,
                    identity_key=identity_exact,
                    max_retries=1,
                    priority=15,
                ),
            )
            trap.assert_enqueued_job(
                self.env["test.queue.job"].testing_method,
                args=("x",),
                kwargs={"foo": "y"},
            )
            trap.assert_enqueued_job(
                self.env["test.queue.job"].no_description,
            )

            trap.perform_enqueued_jobs()

    def test_trap_jobs_perform(self):
        with trap_jobs() as trap:
            model = self.env["test.queue.job"]
            model.with_delay(priority=1).create_ir_logging(
                "test_trap_jobs_perform single"
            )
            node = Delayable(model).create_ir_logging("test_trap_jobs_perform graph 1")
            node2 = Delayable(model).create_ir_logging("test_trap_jobs_perform graph 2")
            node3 = Delayable(model).create_ir_logging("test_trap_jobs_perform graph 3")
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

            trap.assert_jobs_count(0)

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
            self.env["test.queue.job"].button_that_uses_with_delay()

            self.assertEqual(delayable_cls.call_count, 1)
            # arguments passed in 'with_delay()'
            delay_args, delay_kwargs = delayable_cls.call_args
            self.assertEqual(delay_args, (self.env["test.queue.job"],))
            self.assertDictEqual(
                delay_kwargs,
                {
                    "channel": "root.test",
                    "description": "Test",
                    "eta": 15,
                    "identity_key": identity_exact,
                    "max_retries": 1,
                    "priority": 15,
                },
            )

            # check what's passed to the job method 'testing_method'
            self.assertEqual(delayable.testing_method.call_count, 1)
            delay_args, delay_kwargs = delayable.testing_method.call_args
            self.assertEqual(delay_args, (1,))
            self.assertDictEqual(delay_kwargs, {"foo": 2})

    @mute_logger("odoo.addons.queue_job.utils")
    @mock.patch.dict(os.environ, {"QUEUE_JOB__NO_DELAY": "1"})
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

    @mute_logger("odoo.addons.queue_job.utils")
    def test_delay_graph_direct_exec_context_key(self):
        node = Delayable(
            self.env["test.queue.job"].with_context(queue_job__no_delay=True)
        ).create_ir_logging("test_delay_graph_direct_exec 1")
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

    @mute_logger("odoo.addons.queue_job.utils")
    @mock.patch.dict(os.environ, {"QUEUE_JOB__NO_DELAY": "1"})
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

    @mute_logger("odoo.addons.queue_job.utils")
    def test_delay_with_delay_direct_exec_context_key(self):
        model = self.env["test.queue.job"].with_context(queue_job__no_delay=True)
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
