# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
import os
import threading
from unittest.mock import patch

from odoo.tests import BaseCase, tagged

from odoo.addons.queue_job.jobrunner import START_DELAY, QueueJobRunnerThread, runner

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

    def test_runner_stop_interrupts_the_recovery_delay(self):
        """A runner that lost the master election stops without sleeping it out.

        The server joins the runner thread on shutdown, so a stop waiting for
        ERROR_RECOVERY_DELAY held the whole process for up to 5 seconds.
        """
        a_runner = runner.QueueJobRunner.from_environ_or_config()
        election_lost = threading.Event()

        def initialize_databases():
            election_lost.set()
            raise runner.MasterElectionLost("held by another runner")

        with patch.object(
            a_runner, "initialize_databases", side_effect=initialize_databases
        ):
            thread = threading.Thread(target=a_runner.run, daemon=True)
            thread.start()
            self.addCleanup(thread.join)
            self.assertTrue(election_lost.wait(timeout=5))
            a_runner.stop()
            thread.join(timeout=runner.ERROR_RECOVERY_DELAY / 2)
            self.assertFalse(thread.is_alive())

    def test_runner_thread_stop_interrupts_the_start_delay(self):
        thread = QueueJobRunnerThread()
        thread.start()
        self.addCleanup(thread.join)
        thread.stop()
        thread.join(timeout=START_DELAY / 2)
        self.assertFalse(thread.is_alive())
