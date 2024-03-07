# Copyright 2023 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import fields, models
from odoo.tools import safe_eval


class QueueJobConsumerMixin(models.AbstractModel):
    """Provide common features to models using jobs."""

    _name = "queue.job.consumer.mixin"
    _description = _name

    job_ids = fields.Many2many(
        string="Related jobs",
        comodel_name="queue.job",
        column1="rec_id",
        column2="job_id",
    )

    def _collect_queue_job(self, qjob):
        """Update job relation w/ queue jobs."""
        for rec in self:
            rec.job_ids |= qjob

    def action_view_related_jobs(self):
        self.ensure_one()
        xmlid = "queue_job.action_queue_job"
        action = self.env["ir.actions.act_window"]._for_xml_id(xmlid)
        action["domain"] = [("id", "in", self.job_ids.ids)]
        # Purge default search filters from ctx to avoid hiding records
        ctx = action.get("context", {})
        if isinstance(ctx, str):
            ctx = safe_eval.safe_eval(ctx, self.env.context)
        action["context"] = {
            k: v for k, v in ctx.items() if not k.startswith("search_default_")
        }
        # Drop ID otherwise the context will be loaded from the action's record
        action.pop("id")
        return action
