# Copyright 2013-2020 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import _, fields, models
from odoo.exceptions import UserError


class QueueTerminateJob(models.TransientModel):
    _name = "queue.terminate.job"
    _description = "Wizard to terminate a job"

    def _default_job_ids(self):
        res = []
        context = self.env.context
        if context.get("active_model") == "queue.job" and context.get("active_ids"):
            res = context["active_ids"]

        # Filter out jobs not in 'started' state
        res = (
            self.env["queue.job"]
            .browse(res)
            .filtered(lambda qj: qj.state == "started" and qj.db_txid)
            .ids
        )

        return res

    job_ids = fields.Many2many(
        comodel_name="queue.job", string="Jobs", default=lambda r: r._default_job_ids()
    )

    def terminate(self):
        failed = self.job_ids.terminate(raise_error=False)
        if failed:
            raise UserError(
                _("Failed to terminate the following jobs:\n%s")
                % "\n- ".join(failed.mapped("uuid"))
            )
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
