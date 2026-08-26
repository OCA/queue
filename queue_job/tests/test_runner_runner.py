# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
import doctest
import os
from unittest import mock

from odoo.tests import BaseCase, tagged

# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
from odoo.addons.queue_job.jobrunner import runner


@tagged("doctest")
class TestDoctest(BaseCase):
    def test_doctest(self):
        doctest.testmod(
            runner, exclude_empty=True, optionflags=doctest.REPORT_ONLY_FIRST_FAILURE
        )


@tagged("-at_install", "post_install")
class TestRunner(BaseCase):
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

    def test_max_capacity_from_env_channels(self):
        with (
            mock.patch.dict(
                os.environ, {"ODOO_QUEUE_JOB_CHANNELS": "root:7,sub:2"}, clear=True
            ),
            mock.patch.object(runner, "queue_job_config", {}),
        ):
            self.assertEqual(runner._max_capacity(), 7)

    def test_max_capacity_from_env_channels_without_root(self):
        with (
            mock.patch.dict(
                os.environ, {"ODOO_QUEUE_JOB_CHANNELS": "sub:2"}, clear=True
            ),
            mock.patch.object(runner, "queue_job_config", {}),
        ):
            self.assertEqual(runner._max_capacity(), 1)

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
