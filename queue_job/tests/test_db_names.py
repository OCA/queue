from odoo.tests.common import TransactionCase
from odoo.tools import config

class TestGetDbNames(TransactionCase):

    def test_get_db_names(self):
        os.environ["ODOO_QUEUE_JOB_JOBRUNNER_DB_NAME"] = "db1,db2"
        config["db_name"] = False
        queue_job_config = {"jobrunner_db_name": "db3,db4"}

        db_names = self.env["queue.job"].get_db_names()
        self.assertEqual(db_names, ["db1", "db2"])

        os.environ["ODOO_QUEUE_JOB_JOBRUNNER_DB_NAME"] = False

        db_names = self.env["queue.job"].get_db_names()
        self.assertEqual(db_names, ["db3", "db4"])

