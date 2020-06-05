#  Copyright (c) Akretion 2020
#  License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import api, fields, models

from odoo.addons.queue_job.job import job


class QueueJobChunk(models.Model):
    _name = "queue.job.chunk"
    _description = "Queue Job Chunk"
    _inherit = "collection.base"

    @api.depends("model_name", "record_id")
    def _compute_reference(self):
        for rec in self:
            rec.company_id = self.env.user.company_id
            if rec.model_name and rec.record_id:
                rec.reference = "{},{}".format(rec.model_name, rec.record_id)
                record = self.env[rec.model_name].browse(rec.record_id)
                if "company_id" in record._fields:
                    rec.company_id = record.company_id
            else:
                rec.reference = None

    # component fields
    usage = fields.Char("Usage")
    apply_on_model = fields.Char("Apply on model")

    data_str = fields.Text(string="Editable data")
    state = fields.Selection(
        [("pending", "Pending"), ("done", "Done"), ("fail", "Failed")],
        default="pending",
        string="State",
    )
    state_info = fields.Text("Additional state information")
    model_name = fields.Char("Model ID")
    record_id = fields.Integer("Record ID")
    reference = fields.Reference(
        selection=[], string="Reference", compute=_compute_reference, store=True
    )
    company_id = fields.Many2one("res.company", compute=_compute_reference, store=True)

    @api.model_create_multi
    def create(self, vals):
        result = super().create(vals)
        for rec in result:
            rec.enqueue_job()
        return result

    def button_retry(self):
        self.enqueue_job()

    def enqueue_job(self):
        return self.with_delay().process_chunk()

    @job
    def process_chunk(self):
        self.ensure_one()
        usage = self.usage
        apply_on = self.apply_on_model
        with self.work_on(apply_on) as work:
            try:
                with self.env.cr.savepoint():
                    processor = work.component(usage=usage)
                    result = processor.run()
            except Exception as e:
                self.state = "fail"
                self.state_info = type(e).__name__ + str(e.args)
                return False
            self.state_info = ""
            self.state = "done"
            return result
