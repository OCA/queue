# Copyright 2024 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models


class QueueJob(models.Model):
    _inherit = "queue.job"

    def _get_web_notify_failure_title(self):
        self.ensure_one()
        return _("Job failed")

    def _get_web_notify_failure_message(self):
        self.ensure_one()
        return self.display_name

    def _message_post_on_failure(self):
        res = super()._message_post_on_failure()
        for job in self:
            if not job.job_function_id.is_web_notify_failure_enabled:
                continue
            notification_title = job._get_web_notify_failure_title()
            notification_message = job._get_web_notify_failure_message()
            job.user_id.notify_danger(
                message=notification_message, title=notification_title, sticky=True
            )
        return res
