# copyright 2020 Camptocamp
# license lgpl-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import exceptions
from odoo.tests import common
from odoo.tools import mute_logger


class TestJobCreatePrivate(common.HttpCase):
    def test_create_error(self):
        self.authenticate("admin", "admin")
        with self.assertRaises(common.JsonRpcException) as cm, mute_logger("odoo.http"):
            self.make_jsonrpc_request(
                "/web/dataset/call_kw",
                params={
                    "model": "queue.job",
                    "method": "create",
                    "args": [],
                    "kwargs": {
                        "method_name": "write",
                        "model_name": "res.partner",
                        "uuid": "test",
                    },
                },
                headers={
                    "Cookie": f"session_id={self.session.sid};",
                },
            )
        self.assertEqual("odoo.exceptions.AccessError", str(cm.exception))


class TestJobWriteProtected(common.TransactionCase):
    def test_write_protected_field_error(self):
        job_ = self.env["res.partner"].with_delay().create({"name": "test"})
        db_job = job_.db_record()
        with self.assertRaises(exceptions.AccessError):
            db_job.method_name = "unlink"

    def test_write_allow_no_protected_field_error(self):
        job_ = self.env["res.partner"].with_delay().create({"name": "test"})
        db_job = job_.db_record()
        db_job.priority = 30
        self.assertEqual(db_job.priority, 30)
