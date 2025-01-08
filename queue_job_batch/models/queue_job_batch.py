# Copyright 2019 Creu Blanca
# Copyright 2023 ForgeFlow S.L. (http://www.forgeflow.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models

from odoo.addons.mail.tools.discuss import Store


class QueueJobBatch(models.Model):
    _name = "queue.job.batch"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Batch of jobs"
    _log_access = False

    name = fields.Char(
        required=True,
        readonly=True,
        tracking=True,
    )
    job_ids = fields.One2many(
        "queue.job",
        inverse_name="job_batch_id",
        readonly=True,
    )
    job_count = fields.Integer(
        compute="_compute_job_count",
    )
    user_id = fields.Many2one(
        "res.users",
        required=True,
        readonly=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("enqueued", "Enqueued"),
            ("progress", "In Progress"),
            ("finished", "Finished"),
        ],
        default="pending",
        required=True,
        readonly=True,
        tracking=True,
    )
    finished_job_count = fields.Float(
        compute="_compute_job_count",
    )
    failed_job_count = fields.Float(
        compute="_compute_job_count",
    )
    company_id = fields.Many2one(
        "res.company",
        readonly=True,
    )
    is_read = fields.Boolean()
    completeness = fields.Float(
        compute="_compute_job_count",
    )
    failed_percentage = fields.Float(
        compute="_compute_job_count",
    )

    def _get_state(self):
        self.ensure_one()
        job_states = set(self.job_ids.grouped("state").keys())
        if all(state in ("done", "cancelled", "failed") for state in job_states):
            return "finished"
        elif {"done", "started"} & job_states:
            return "progress"
        elif "enqueued" in job_states:
            return "enqueued"
        return "pending"

    def check_state(self):
        for rec in self:
            if (state := rec._get_state()) != rec.state:
                rec.state = state

    def set_read(self):
        for rec in self:
            if rec.is_read or rec.state != "finished":
                continue
            rec.is_read = True
            rec.user_id._bus_send("queue.job.batch/updated", {"batch_read": True})

    @api.model
    def get_new_batch(self, name, **kwargs):
        vals = kwargs.copy()
        vals.update(
            {
                "user_id": self.env.uid,
                "name": name,
                "company_id": self.env.company.id or self.env.user.company_id.id,
            }
        )
        record = self.sudo().create(vals).with_user(self.env.uid)
        record.user_id._bus_send("queue.job.batch/updated", {"batch_created": True})
        return record

    @api.depends("job_ids.state")
    def _compute_job_count(self):
        for rec in self:
            jobs_by_state = rec.job_ids.grouped("state")
            rec.job_count = len(rec.job_ids)
            rec.failed_job_count = len(jobs_by_state.get("failed", []))
            rec.finished_job_count = len(jobs_by_state.get("done", []))
            rec.completeness = rec.finished_job_count / max(1, rec.job_count)
            rec.failed_percentage = rec.failed_job_count / max(1, rec.job_count)

    @api.model
    def _to_store_fnames(self):
        return (
            "name",
            "state",
            "job_count",
            "finished_job_count",
            "failed_job_count",
            "completeness",
            "failed_percentage",
        )

    def _to_store(self, store: Store):
        fnames = self._to_store_fnames()
        for rec in self:
            data = rec.read(fnames)[0]
            store.add(rec, data)
