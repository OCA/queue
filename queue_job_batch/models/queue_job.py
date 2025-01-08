# Copyright 2019 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models

from odoo.addons.queue_job.job import identity_exact


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
        if vals.get("state", "") == "done":
            batches = self.env["queue.job.batch"]
            for record in self:
                if record.state != "done" and record.job_batch_id:
                    batches |= record.job_batch_id
            for batch in batches:
                # We need to make it with delay in order to prevent two jobs
                # to work with the same batch
                batch.with_delay(identity_key=identity_exact).check_state()
        return super().write(vals)
