# Copyright 2019 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class QueueJob(models.Model):
    _inherit = "queue.job"

    job_batch_id = fields.Many2one("queue.job.batch")

    @api.model
    def create(self, vals):
        batch = self.env.context.get("job_batch")
        if batch and isinstance(batch, models.Model) and batch.state == "draft":
            vals.update({"job_batch_id": batch.id})
        return super().create(vals)

    def write(self, vals):
        batches = self.env["queue.job.batch"]
        for record in self:
            if (
                record.job_batch_id
                and record.state != "done"
                and vals.get("state", "") == "done"
            ):
                batches |= record.job_batch_id
        for batch in batches:
            # We need to make it with delay in order to prevent two jobs
            # to work with the same batch
            batch.with_delay().check_state()
        return super().write(vals)
