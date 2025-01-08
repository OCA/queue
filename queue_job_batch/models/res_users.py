# Copyright 2025 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class Users(models.Model):
    _name = "res.users"
    _inherit = ["res.users"]

    def _init_store_data(self, store):
        res = super()._init_store_data(store)
        store.add(
            {
                "hasQueueJobBatchUserGroup": self.env.user.has_group(
                    "queue_job_batch.group_queue_job_batch_user"
                ),
            }
        )
        return res

    def _get_queue_job_batches(self):
        # See :meth:`controllers.webclient.WebClient._process_request_for_internal_user`
        self.ensure_one()
        return self.env["queue.job.batch"].search(
            [
                ("user_id", "=", self.id),
                ("is_read", "=", False),
            ]
        )
