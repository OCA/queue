# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.modules.module import get_manifest as real_get_manifest
from odoo.tests.common import TransactionCase

from ..controllers import main as main_module
from ..controllers.main import RunJobController
from ..job import Job

_CTRL_MOD = "odoo.addons.queue_job.controllers.main"


class TestRunJobController(TransactionCase):
    def setUp(self):
        super().setUp()
        # _worker_is_outdated() caches its verdict in a process-level global,
        # not per-transaction -- TransactionCase's rollback between tests has
        # no way to clear it, so each test must start from a clean cache.
        main_module._modules_up_to_date_cache.clear()

    def test_get_failure_values(self):
        method = self.env["res.users"].mapped
        job = Job(method)
        ctrl = RunJobController()
        rslt = ctrl._get_failure_values(job, "info", Exception("zero", "one"))
        self.assertEqual(
            rslt, {"exc_info": "info", "exc_name": "Exception", "exc_message": "zero"}
        )

    def test_runjob_success(self):
        job = self.env["queue.job"].with_delay()._test_job()
        RunJobController._runjob(self.env, job)
        self.assertEqual(job.state, "done")
        self.assertEqual(job.db_record().state, "done")

    def test_runjob_postpones_when_worker_outdated(self):
        """When the worker's module code is outdated, the job is postponed
        instead of executed, and _try_perform_job is never reached."""
        # job.store() here runs inside job.in_temporary_env(), which commits
        # on its own separate cursor (job.py) so a postponed job survives
        # even if its own transaction rolls back -- meaning this row also
        # survives TransactionCase's rollback. Clean it up the same way.
        job = self.env["queue.job"].with_delay()._test_job()
        self.addCleanup(self._delete_committed_job, job.uuid)
        with patch.object(RunJobController, "_worker_is_outdated", return_value=True):
            with patch.object(RunJobController, "_try_perform_job") as mock_perform:
                RunJobController._runjob(self.env, job)
        mock_perform.assert_not_called()
        self.assertEqual(job.state, "pending")
        self.assertEqual(job.db_record().state, "pending")

    def _delete_committed_job(self, uuid):
        with self.env.registry.cursor() as cr:
            cr.execute("DELETE FROM queue_job WHERE uuid = %s", (uuid,))

    def test_worker_is_outdated_false_by_default(self):
        """A freshly installed test DB is never outdated: on-disk versions
        already match what was recorded in the database."""
        # A fresh test DB has every installed module's on-disk version
        # matching what was recorded at install time -- no setup needed.
        self.assertFalse(RunJobController._worker_is_outdated(self.env))

    def test_worker_is_outdated_true_on_mismatch(self):
        """A module whose recorded latest_version differs from its on-disk
        manifest version is detected as outdated."""
        base = (
            self.env["ir.module.module"].sudo().search([("name", "=", "base")], limit=1)
        )
        base.write({"latest_version": "0.0.0"})
        self.assertTrue(RunJobController._worker_is_outdated(self.env))

    def test_worker_is_outdated_ignores_unreadable_manifest(self):
        """A module whose manifest can't be read from disk is skipped, not
        treated as evidence of staleness."""

        def fake_get_manifest(module_name, mod_path=None):
            if module_name == "base":
                return {}
            return real_get_manifest(module_name, mod_path)

        with patch(_CTRL_MOD + ".get_manifest", side_effect=fake_get_manifest):
            # "base"'s manifest is unreadable here, but nothing else is
            # actually mismatched -- must not be treated as outdated.
            self.assertFalse(RunJobController._worker_is_outdated(self.env))

    def test_worker_is_outdated_disabled_via_config_param(self):
        """Setting queue_job.check_modules_up_to_date to False skips the
        check entirely, even with a real version mismatch present."""
        base = (
            self.env["ir.module.module"].sudo().search([("name", "=", "base")], limit=1)
        )
        base.write({"latest_version": "0.0.0"})
        self.env["ir.config_parameter"].sudo().set_param(
            "queue_job.check_modules_up_to_date", "False"
        )
        self.assertFalse(RunJobController._worker_is_outdated(self.env))

    def test_worker_is_outdated_result_is_cached(self):
        """The outdated verdict is cached per database for a few seconds,
        and only recomputed once that cache entry is expired."""
        base = (
            self.env["ir.module.module"].sudo().search([("name", "=", "base")], limit=1)
        )
        original_latest_version = base.latest_version
        base.write({"latest_version": "0.0.0"})
        self.assertTrue(RunJobController._worker_is_outdated(self.env))

        # Fix the mismatch -- the cached verdict should still say True.
        base.write({"latest_version": original_latest_version})
        self.assertTrue(RunJobController._worker_is_outdated(self.env))

        # Force the cache entry to look expired -> recompute -> now False.
        dbname = self.env.cr.dbname
        main_module._modules_up_to_date_cache[dbname] = (0.0, True)
        self.assertFalse(RunJobController._worker_is_outdated(self.env))
