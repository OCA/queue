# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import HttpCase, TransactionCase

from ..controllers.main import RunJobController
from ..job import Job
from ..models.queue_job import QueueJob


class TestRunJobController(TransactionCase):
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


class TestRunJobControllerHttp(HttpCase):
    def test_runjob_http_repairs_default_env(self):
        """A job run through the real /queue_job/runjob (auth=none) route
        must leave `transaction.default_env` on a valid, real user.

        `IrHttp._auth_method_none()` forces `transaction.default_env` to an
        environment with `uid=None` before the controller runs. Any
        `env.user` access during a savepoint-triggered flush inside the job
        (e.g. a recompute/constrain calling `has_group`) then raises
        "Expected singleton: res.users()" because `browse(None)` is empty.
        """

        def _test_job(self):
            with self.env.cr.savepoint():
                pass
            # Would raise "Expected singleton: res.users()" without the fix.
            self.env.transaction.default_env.user.ensure_one()

        self.patch(QueueJob, "_test_job", _test_job)
        job_ = self.env["queue.job"].with_delay()._test_job()
        job_.set_enqueued()
        job_.store()
        db_job = job_.db_record()
        response = self.url_open(
            f"/queue_job/runjob?db={self.env.cr.dbname}&job_uuid={db_job.uuid}"
        )
        self.assertEqual(response.status_code, 200)
        db_job.invalidate_recordset()
        self.assertEqual(db_job.state, "done", db_job.exc_info)
