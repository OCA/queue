# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from psycopg2 import OperationalError, errorcodes

from odoo.tests.common import TransactionCase

from ..controllers.main import RunJobController, _concurrency_error
from ..exception import RetryableJobError
from ..job import Job


class SerializationFailure(OperationalError):
    pgcode = errorcodes.SERIALIZATION_FAILURE


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

    def test_concurrency_error_wrapped_in_another_error(self):
        original = SerializationFailure("could not serialize access")
        wrapped = ValueError("wrapped")
        wrapped.__context__ = original
        self.assertIs(_concurrency_error(wrapped), original)

    def test_other_errors_are_not_concurrency_errors(self):
        self.assertIsNone(_concurrency_error(ValueError("business error")))

    def test_job_errors_are_not_concurrency_errors(self):
        error = RetryableJobError("retry later")
        error.__context__ = SerializationFailure("could not serialize access")
        self.assertIsNone(_concurrency_error(error))
