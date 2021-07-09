# Copyright 2016 Cédric Pigeon
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import odoo.tests.common as common

from odoo.addons.queue_job.job import Job


class TestJobSubscribe(common.TransactionCase):
    def setUp(self):
        super(TestJobSubscribe, self).setUp()
        grp_queue_job_manager = self.ref("queue_job.group_queue_job_manager")
        self.other_partner_a = self.env["res.partner"].create(
            {"name": "My Company a", "is_company": True, "email": "test@tes.ttest"}
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
            {"name": "My Company b", "is_company": True, "email": "test@tes.ttest"}
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
        method = self.env["res.users"].with_user(self.other_user_a).mapped
        test_job = Job(method)
        test_job.store()
        test_job_record = self.env["queue.job"].search([("uuid", "=", test_job.uuid)])
        test_job_record.write({"state": "failed"})
        return test_job_record

    def test_job_subscription(self):
        """
        When a job is created, all user of group
        queue_job.group_queue_job_manager are automatically set as
        follower except if the flag subscribe_job is not set
        """

        #################################
        # Test 1: All users are followers
        #################################
        stored = self._create_failed_job()
        users = self.env["res.users"].search(
            [("groups_id", "=", self.ref("queue_job.group_queue_job_manager"))]
        )
        self.assertEqual(len(stored.message_follower_ids), len(users))
        expected_partners = [u.partner_id for u in users]
        self.assertSetEqual(
            set(stored.mapped("message_follower_ids.partner_id")),
            set(expected_partners),
        )
        followers_id = [f.id for f in stored.mapped("message_follower_ids.partner_id")]
        self.assertIn(self.other_partner_a.id, followers_id)
        self.assertIn(self.other_partner_b.id, followers_id)

        ###########################################
        # Test 2: User b request to not be follower
        ###########################################
        self.other_user_b.write({"subscribe_job": False})
        stored = self._create_failed_job()
        users = self.env["res.users"].search(
            [
                ("groups_id", "=", self.ref("queue_job.group_queue_job_manager")),
                ("subscribe_job", "=", True),
            ]
        )
        self.assertEqual(len(stored.message_follower_ids), len(users))
        expected_partners = [u.partner_id for u in users]
        self.assertSetEqual(
            set(stored.mapped("message_follower_ids.partner_id")),
            set(expected_partners),
        )
        followers_id = [f.id for f in stored.mapped("message_follower_ids.partner_id")]
        self.assertIn(self.other_partner_a.id, followers_id)
        self.assertNotIn(self.other_partner_b.id, followers_id)
