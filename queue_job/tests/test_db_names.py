import os
from odoo.tests.common import TransactionCase
from odoo.tools import config

class TestGetDbNames(TransactionCase):

    def test_get_db_names(self):
        os.environ["ODOO_QUEUE_JOB_JOBRUNNER_DB_NAME"] = "db1,db2"
        config["db_name"] = False

        db_names = self.env["queue.job"].get_db_names()
        self.assertEqual(db_names, ["db1", "db2"])

