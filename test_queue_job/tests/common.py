# Copyright 2016-2019 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import Command
from odoo.tests import common

from odoo.addons.queue_job.job import Job


class JobCommonCase(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.queue_job = cls.env["queue.job"]
        cls.user = cls.env["res.users"]
        cls.method = cls.env["test.queue.job"].testing_method
        company = cls.env.ref("base.main_company")
        cls.demo_user = cls.user.create(
            {
                "name": "Demo User",
                "login": "demo_demo_demo",
                "company_id": company.id,
                "company_ids": [Command.set(company.ids)],
                "group_ids": [Command.set(cls.env.ref("base.group_user").ids)],
            }
        )

    def _create_job(self):
        test_job = Job(self.method)
        test_job.store()
        stored = Job.db_records_from_uuids(self.env, [test_job.uuid])
        self.assertEqual(len(stored), 1)
        return stored
