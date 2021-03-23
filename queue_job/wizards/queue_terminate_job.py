# Copyright 2013-2020 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import fields, models
from odoo.exceptions import UserError


class QueueTerminateJob(models.TransientModel):
    _name = "queue.terminate.job"
    _description = "Wizard to terminate a job"

    def _default_job_ids(self):
        res = False
        context = self.env.context
        if context.get("active_model") == "queue.job" and context.get("active_ids"):
            res = context["active_ids"]
        return res

    job_ids = fields.Many2many(
        comodel_name="queue.job", string="Jobs", default=lambda r: r._default_job_ids()
    )

    def terminate(self):
        failed = self.job_ids.terminate()
        if failed:
            raise UserError(
                "Failed to terminate the following jobs:%s" %
                "\n- ".join(failed.mapped("uuid"))
            )
        return {"type": "ir.actions.act_window_close"}
