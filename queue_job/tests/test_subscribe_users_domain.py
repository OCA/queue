# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import Command
from odoo.tests import common


class TestSubscribeUsersDomain(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_user = cls.env.ref("base.group_user")
        manager_group = cls.env.ref("queue_job.group_queue_job_manager")
        implying_group = cls.env["res.groups"].create(
            {
                "name": "Implies Job Queue Manager",
                "implied_ids": [Command.link(manager_group.id)],
            }
        )
        Users = cls.env["res.users"]
        cls.direct_manager = Users.create(
            {
                "name": "Direct Queue Manager",
                "login": "queue_direct_manager",
                "group_ids": [Command.set([group_user.id, manager_group.id])],
            }
        )
        cls.implied_manager = Users.create(
            {
                "name": "Implied Queue Manager",
                "login": "queue_implied_manager",
                "group_ids": [Command.set([group_user.id, implying_group.id])],
            }
        )

    def test_subscribe_users_domain_includes_implied_managers(self):
        domain = self.env["queue.job"]._subscribe_users_domain()
        users = self.env["res.users"].search(domain)
        self.assertIn(self.direct_manager, users)
        self.assertIn(self.implied_manager, users)
