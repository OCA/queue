# Copyright 2019 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class QueueJob(models.Model):
    _inherit = "queue.job"

    job_batch_id = fields.Many2one("queue.job.batch")

    @api.model_create_multi
    def create(self, vals_list):
        batch = self.env.context.get("job_batch")
        if batch and isinstance(batch, models.Model):
            for vals in vals_list:
                vals.update({"job_batch_id": batch.id})
        return super().create(vals_list)

    def write(self, vals):
        new_state = vals.get("state", "")
        # Trigger check_state for any terminal state (done, cancelled, failed)
        if new_state in ("done", "cancelled", "failed"):
            batches = self.env["queue.job.batch"]
            for record in self:
                # Only trigger if the job wasn't already in a terminal state
                if (
                    record.state not in ("done", "cancelled", "failed")
                    and record.job_batch_id
                ):
                    batches |= record.job_batch_id
            for batch in batches:
                # Run check_state without identity_key to prevent race condition
                # where deduplication causes the last job's check_state to be skipped
                batch.with_delay().check_state()
        return super().write(vals)
