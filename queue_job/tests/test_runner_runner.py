# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
import os
from unittest.mock import patch

from odoo.tests import BaseCase, tagged

from odoo.addons.queue_job import jobrunner as jobrunner_bootstrap
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

    def test_jobrunner_target_uses_odoo_sh_dev_domain(self):
        with patch.dict(os.environ, {"ODOO_STAGE": "dev"}, clear=False):
            self.assertEqual(
                ("https", "jb-web-feat-jb-paddle-31042512.dev.odoo.com", 443),
                runner._jobrunner_target("jb-web-feat-jb-paddle-31042512"),
            )

    def test_jobrunner_target_uses_odoo_sh_staging_domain(self):
        with patch.dict(os.environ, {"ODOO_STAGE": "staging"}, clear=False):
            self.assertEqual(
                (
                    "https",
                    "getbasher-jigglebee-web-staging-30747585.dev.odoo.com",
                    443,
                ),
                runner._jobrunner_target("getbasher-jigglebee-web-staging-30747585"),
            )

    def test_jobrunner_target_uses_odoo_sh_production_domain(self):
        with patch.dict(os.environ, {"ODOO_STAGE": "production"}, clear=False):
            self.assertEqual(
                ("https", "jb-web.odoo.com", 443),
                runner._jobrunner_target("jb-web"),
            )

    def test_jobrunner_target_prefers_explicit_values_on_odoo_sh(self):
        with patch.dict(os.environ, {"ODOO_STAGE": "staging"}, clear=False):
            self.assertEqual(
                ("https", "custom.example.com", 8443),
                runner._jobrunner_target(
                    "getbasher-jigglebee-web-staging-30747585",
                    scheme="https",
                    host="custom.example.com",
                    port=8443,
                ),
            )

    def test_should_start_runner_thread_lazily_on_odoosh_http_process(self):
        with patch.object(jobrunner_bootstrap, "_is_runner_enabled", return_value=True):
            self.assertTrue(
                jobrunner_bootstrap._should_start_runner_thread_lazily(
                    stage="staging",
                    stop_after_init=False,
                    http_enable=True,
                    server_wide_modules=["base", "web"],
                )
            )

    def test_should_not_start_runner_thread_lazily_when_server_wide(self):
        with patch.object(jobrunner_bootstrap, "_is_runner_enabled", return_value=True):
            self.assertFalse(
                jobrunner_bootstrap._should_start_runner_thread_lazily(
                    stage="production",
                    stop_after_init=False,
                    http_enable=True,
                    server_wide_modules=["base", "web", "queue_job"],
                )
            )

    def test_maybe_start_runner_thread_starts_only_once(self):
        original_runner_thread = jobrunner_bootstrap.runner_thread
        try:
            jobrunner_bootstrap.runner_thread = None
            fake_thread = type("FakeThread", (), {"start": lambda self: None})()
            with (
                patch.object(
                    jobrunner_bootstrap,
                    "_should_start_runner_thread_lazily",
                    return_value=True,
                ),
                patch.object(
                    jobrunner_bootstrap,
                    "QueueJobRunnerThread",
                    return_value=fake_thread,
                ) as thread_cls,
            ):
                self.assertTrue(
                    jobrunner_bootstrap.maybe_start_runner_thread("lazy http worker")
                )
                self.assertFalse(
                    jobrunner_bootstrap.maybe_start_runner_thread("lazy http worker")
                )
                self.assertEqual(1, thread_cls.call_count)
        finally:
            jobrunner_bootstrap.runner_thread = original_runner_thread
