#  Copyright (c) Akretion 2020
#  License AGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import json
import traceback

from psycopg2 import OperationalError

from odoo import api, fields, models
from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY

from odoo.addons.queue_job.exception import RetryableJobError

# Use to bypass chunks entirely for easier debugging
DEBUG_MODE = False


class QueueJobChunk(models.Model):
    _name = "queue.job.chunk"
    _description = "Queue Job Chunk"
    _order = "id desc"

    processor = fields.Selection([])
    data_str = fields.Text(string="Editable data")
    state = fields.Selection(
        [("pending", "Pending"), ("done", "Done"), ("fail", "Failed")],
        default="pending",
        readonly=True,
    )
    state_info = fields.Text("Additional state information", readonly=True)
    model_name = fields.Char(readonly=True)
    record_id = fields.Integer(readonly=True)
    reference = fields.Reference(
        selection="_selection_target_model",
        compute="_compute_reference",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        compute="_compute_reference",
        store=True,
        readonly=True,
    )
    stack_trace = fields.Text(readonly=True)

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

    def _get_processor(self):
        # return here whatever class you want
        # it can be a pure python class, an odoo TransientModel ...
        raise NotImplementedError

    def _get_data(self):
        return json.loads(self.data_str)

    def process_chunk(self):
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                processor = self._get_processor()
                result = processor.run()
        except RetryableJobError:
            raise
        except Exception as e:
            if DEBUG_MODE:
                raise
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
