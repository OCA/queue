# Copyright 2022 ForgeFlow S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import odoo.tests.common as common

from odoo.addons.queue_job.job import Job


class TestJobActivity(common.TransactionCase):
    def setUp(self):
        super(TestJobActivity, self).setUp()
        grp_queue_job_manager = self.ref("queue_job.group_queue_job_manager")
        self.other_partner_a = self.env["res.partner"].create(
            {
                "name": "My Company a",
                "is_company": True,
                "email": "test@tes.ttest",
            }
        )
        self.other_user_a = self.env["res.users"].create(
            {
                "partner_id": self.other_partner_a.id,
                "login": "my_login a",
                "name": "my user",
                "groups_id": [(4, grp_queue_job_manager)],
            }
        )
        self.other_partner_b = self.env["res.partner"].create(
            {
                "name": "My Company b",
                "is_company": True,
                "email": "test@tes.ttest",
            }
        )
        self.other_user_b = self.env["res.users"].create(
            {
                "partner_id": self.other_partner_b.id,
                "login": "my_login_b",
                "name": "my user 1",
                "groups_id": [(4, grp_queue_job_manager)],
            }
        )

    def _create_failed_job(self):
        method = self.env["res.users"].mapped
        test_job = Job(method)
        test_job.store()
        test_job_record = self.env["queue.job"].search([("uuid", "=", test_job.uuid)])
        test_job_record.write({"state": "failed"})
        return test_job_record

    def test_01_job_activity_disabled(self):
        """
        When a job is created,
        activity is assigned to Connector managers
        except if the flag job_activity is not setin the user
        """

        users = self.env["res.users"].search(
            [
                (
                    "groups_id",
                    "=",
                    self.ref("queue_job.group_queue_job_manager"),
                ),
            ]
        )
        users.write({"job_activity": False})
        responsible = self.env["res.users"].create(
            {
                "name": "Hard worker",
                "login": "hardhard",
                "groups_id": [(4, self.ref("queue_job.group_queue_job_manager"))],
                "job_activity": True,
            }
        )
        failed_job = self._create_failed_job()
        activity = self.env["mail.activity"].search(
            [
                ("res_id", "=", failed_job.id),
                (
                    "res_model_id",
                    "=",
                    self.env.ref("queue_job.model_queue_job").id,
                ),
            ]
        )
        self.assertFalse(activity.user_id.id in users.ids)
        self.assertEqual(activity.user_id.id, responsible.id)
