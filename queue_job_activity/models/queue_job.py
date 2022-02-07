# Copyright 2022 ForgeFlow S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class QueueJob(models.Model):
    _inherit = "queue.job"

    @api.multi
    def _activities_users_domain(self):
        group = self.env.ref("queue_job.group_queue_job_manager")
        if not group:
            return None
        companies = self.mapped("company_id")
        domain = [("groups_id", "=", group.id)]
        if companies:
            domain.append(("company_id", "child_of", companies.ids))
        domain.append(("job_activity", "=", True))
        return domain

    def _prepare_activity_vals(self, users):
        return {
            "activity_type_id": self.env.ref("mail.mail_activity_data_todo").id,
            "note": self._message_failed_job(),
            "user_id": users[0].id,
            "res_id": self.id,
            "res_model_id": self.env.ref("queue_job.model_queue_job").id,
        }

    def _message_post_on_failure(self):
        """Create an activity on failed jobs
        The first Connector manager is taken unless it is disable in the user
        settings
        """
        res = super(QueueJob, self)._subscribe_users_domain()
        domain = self._activities_users_domain()
        users = self.env["res.users"].search(domain)
        if not users:
            return res
        for record in self:
            activity_vals = record._prepare_activity_vals(users)
            self.env["mail.activity"].sudo().create(activity_vals)
        return res
