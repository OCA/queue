#  Copyright (c) Akretion 2020
#  License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import api, fields, models

from odoo.addons.queue_job.job import job


class QueueJobChunk(models.Model):
    _name = "queue.job.chunk"
    _description = "Queue Job Chunk"

    def _get_default_company_id(self):
        for rec in self:
            if rec.reference:
                if "company_id" in rec.reference._fields:
                    rec.company_id = rec.reference.company_id
                    continue
            rec.company_id = self.env.uid.company_id

    @api.depends("model_id", "record_id")
    def _compute_reference(self):
        for res in self:
            res.reference = "{},{}".format(res.model, res.res_id)

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
    model_id = fields.Char("Model ID")
    record_id = fields.Integer("Record ID")
    reference = fields.Char(string="Reference", selection=_compute_reference)
    company_id = fields.Many2one("res.company", default=_get_default_company_id)

    @api.model_create_multi
    def create(self, vals):
        result = super().create(vals)
        for rec in result:
            rec.enqueue_job()
        return result

    def button_retry(self):
        self.enqueue_job()

    def enqueue_job(self):
        return self.with_delay()._enqueue_job()

    @job
    def _enqueue_job(self):
        self.ensure_one()
        usage = self.usage
        collection = self.env["collection.base"].new()
        apply_on = self.apply_on_model
        with collection.work_on(apply_on) as work:
            processor = work.component(usage=usage)
            try:
                result = processor.run(self.data_str)
            except Exception as e:
                self.state = "fail"
                self.state_info = str(e)
                return False
            self.model_id = result._name
            self.record_id = result.id
            self.state = "done"
            return result
