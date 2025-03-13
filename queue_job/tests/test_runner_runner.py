# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
import os

from odoo.tests import BaseCase, tagged

from odoo.addons.queue_job.jobrunner import runner

from .common import load_doctests

load_tests = load_doctests(runner)


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
