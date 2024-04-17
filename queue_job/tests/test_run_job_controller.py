# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase

from ..controllers.main import RunJobController
from ..job import Job


class TestRunJobController(TransactionCase):
    def test_get_failure_values(self):
        method = self.env["res.users"].mapped
        job = Job(method)
        ctrl = RunJobController()
        rslt = ctrl._get_failure_values(job, "info", Exception("zero", "one"))
        self.assertEqual(
            rslt, {"exc_info": "info", "exc_name": "Exception", "exc_message": "zero"}
        )
