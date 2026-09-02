# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
import doctest
import os
from unittest import mock

from odoo.tests import BaseCase, tagged

from odoo.addons.queue_job.jobrunner import runner

# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
from odoo.addons.queue_job.jobrunner.channels import ChannelConfig, ChannelManager


@tagged("doctest")
class TestDoctest(BaseCase):
    def test_doctest(self):
        doctest.testmod(
            runner, exclude_empty=True, optionflags=doctest.REPORT_ONLY_FIRST_FAILURE
        )


@tagged("-at_install", "post_install")
class TestRunner(BaseCase):
    def setUp(self):
        super().setUp()
        # ensure there is no collision with actual environment variables/config
        env_patcher = mock.patch.dict(
            "os.environ",
            {
                "ODOO_QUEUE_JOB_MAX_CAPACITY": "",
                "ODOO_QUEUE_JOB_DB_MAX_CAPACITY": "",
                "ODOO_QUEUE_JOB_CHANNELS": "",
            },
        )
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

        conf_patcher = mock.patch.object(runner, "queue_job_config", {})
        conf_patcher.start()
        self.addCleanup(conf_patcher.stop)

    def _new_channel_manager(self, jobrunner, db_name, channel_config, pending_jobs=0):
        channel_manager = ChannelManager()
        channel_manager.configure(channel_config)
        jobrunner._register_channel_manager(db_name, channel_manager)
        jobrunner.db_by_name[db_name] = mock.MagicMock(name=f"Database({db_name})")
        for number in range(pending_jobs):
            channel_manager.notify(
                db_name, "root", f"{db_name}-{number}", number, 0, 10, None, "pending"
            )
        return channel_manager

    @classmethod
    def _is_open_file_descriptor(cls, fd):
        try:
            os.fstat(fd)
            return True
        except OSError:
            return False

    def test_runner_file_descriptor(self):
        a_runner = runner.QueueJobRunner.from_environ_or_config()

        read_fd, write_fd = a_runner._stop_pipe
        self.assertTrue(self._is_open_file_descriptor(read_fd))
        self.assertTrue(self._is_open_file_descriptor(write_fd))

        del a_runner

        self.assertFalse(self._is_open_file_descriptor(read_fd))
        self.assertFalse(self._is_open_file_descriptor(write_fd))

    def test_runner_file_closed_read_descriptor(self):
        a_runner = runner.QueueJobRunner.from_environ_or_config()

        read_fd, write_fd = a_runner._stop_pipe
        os.close(read_fd)

        del a_runner

        self.assertFalse(self._is_open_file_descriptor(read_fd))
        self.assertFalse(self._is_open_file_descriptor(write_fd))

    def test_runner_file_closed_write_descriptor(self):
        a_runner = runner.QueueJobRunner.from_environ_or_config()

        read_fd, write_fd = a_runner._stop_pipe
        os.close(write_fd)

        del a_runner

        self.assertFalse(self._is_open_file_descriptor(read_fd))
        self.assertFalse(self._is_open_file_descriptor(write_fd))

    def test_max_capacity_from_env(self):
        with (
            mock.patch.dict(
                os.environ, {"ODOO_QUEUE_JOB_MAX_CAPACITY": "5"}, clear=True
            ),
            mock.patch.object(runner, "queue_job_config", {}),
        ):
            self.assertEqual(runner._max_capacity(), 5)

    def test_max_capacity_from_odoo_config(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(runner, "queue_job_config", {"max_capacity": "3"}),
        ):
            self.assertEqual(runner._max_capacity(), 3)

    def test_max_capacity_env_priority_over_odoo_config(self):
        with (
            mock.patch.dict(
                os.environ, {"ODOO_QUEUE_JOB_MAX_CAPACITY": "5"}, clear=True
            ),
            mock.patch.object(runner, "queue_job_config", {"max_capacity": "3"}),
        ):
            self.assertEqual(runner._max_capacity(), 5)

    def test_max_capacity_default(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(runner, "queue_job_config", {}),
        ):
            self.assertEqual(runner._max_capacity(), 0)

    def test_max_capacity_equals_to_channel_config_string(self):
        jobrunner = runner.QueueJobRunner(channel_config_string="root:3")
        self.assertEqual(jobrunner.max_capacity, 3)

    def test_max_capacity_server_side_has_priority(self):
        jobrunner = runner.QueueJobRunner(
            channel_config_string="root:3", max_capacity=1
        )
        self.assertEqual(jobrunner.max_capacity, 3)

    def test_max_capacity_channel_config_no_root(self):
        jobrunner = runner.QueueJobRunner(channel_config_string="sub:3")
        self.assertEqual(jobrunner.max_capacity, 1)

    def test_no_job_dispatched_when_no_database_channel_manager(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        with mock.patch.object(jobrunner, "_dispatch_job") as dispatch:
            jobrunner.run_jobs()
        dispatch.assert_not_called()

    def test_global_capacity_across_databases(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        manager_a = self._new_channel_manager(
            jobrunner, "db_a", [ChannelConfig("root", 5)], pending_jobs=4
        )
        manager_b = self._new_channel_manager(
            jobrunner, "db_b", [ChannelConfig("root", 5)], pending_jobs=4
        )
        with mock.patch.object(jobrunner, "_dispatch_job") as dispatch:
            jobrunner.run_jobs()
        # number of running jobs must be limited by max_capacity
        self.assertEqual(dispatch.call_count, 3)
        self.assertEqual(manager_a.running_count + manager_b.running_count, 3)
