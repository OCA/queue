#  Copyright (c) Akretion 2020
#  License AGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import traceback

from psycopg2 import OperationalError

from odoo import api, fields, models
from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY

# Use to bypass chunks entirely for easier debugging
DEBUG_MODE = False


class QueueJobChunk(models.Model):
    _name = "queue.job.chunk"
    _description = "Queue Job Chunk"
    _inherit = "collection.base"

    @api.model
    def _selection_target_model(self):
        models = self.env["ir.model"].search([])
        return [(model.model, model.name) for model in models]

    @api.depends("model_name", "record_id")
    def _compute_reference(self):
        for rec in self:
            rec.company_id = self.env.user.company_id
            if rec.model_name and rec.record_id:
                rec.reference = "{},{}".format(rec.model_name, rec.record_id or 0)
                record = self.env[rec.model_name].browse(rec.record_id)
                if "company_id" in record._fields:
                    rec.company_id = record.company_id
            else:
                rec.reference = False

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
        string="Reference",
        selection="_selection_target_model",
        compute=_compute_reference,
        store=True,
    )
    company_id = fields.Many2one("res.company", compute=_compute_reference, store=True)
    stack_trace = fields.Text("Stack trace")

    @api.model_create_multi
    def create(self, vals):
        result = super().create(vals)
        for rec in result:
            rec.enqueue_job()
        return result

    def button_retry(self):
        self.enqueue_job()

    def enqueue_job(self):
        if DEBUG_MODE:
            return self.process_chunk()
        else:
            return self.with_delay().process_chunk()

    def process_chunk(self):
        self.ensure_one()
        usage = self.usage
        apply_on = self.apply_on_model
        with self.work_on(apply_on) as work:
            if DEBUG_MODE:
                with self.env.cr.savepoint():
                    processor = work.component(usage=usage)
                    result = processor.run()
                    self.state_info = ""
                    self.state = "done"
                    return result
            else:
                try:
                    with self.env.cr.savepoint():
                        processor = work.component(usage=usage)
                        result = processor.run()
                except Exception as e:
                    # TODO maybe it will be simplier to have a kind of inherits
                    #  on queue.job to avoid a double error management
                    # so a failling chunk will have a failling job
                    if (
                        isinstance(e, OperationalError)
                        and e.pgcode in PG_CONCURRENCY_ERRORS_TO_RETRY
                    ):
                        # In that case we raise an error so queue_job
                        # will do a RetryableJobError
                        raise
                    self.state = "fail"
                    self.state_info = type(e).__name__ + str(e.args)
                    self.stack_trace = traceback.format_exc()
                    return False
                self.state_info = ""
                self.state = "done"
                return result
