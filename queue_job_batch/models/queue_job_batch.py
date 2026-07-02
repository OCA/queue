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

    def _get_state(self, job_states):
        """Determine the batch state from a set of job states.

        :param job_states: set of state strings for all jobs in this batch
        """
        if all(state in ("done", "cancelled", "failed") for state in job_states):
            return "finished"
        elif {"done", "started"} & job_states:
            return "progress"
        elif "enqueued" in job_states:
            return "enqueued"
        return "pending"

    def check_state(self):
        grouped = self.env["queue.job"].read_group(
            [("job_batch_id", "in", self.ids)],
            ["job_batch_id", "state"],
            ["job_batch_id", "state"],
            lazy=False,
        )
        states_by_batch = {}
        for g in grouped:
            batch_id = g["job_batch_id"][0]
            states_by_batch.setdefault(batch_id, set()).add(g["state"])

        for rec in self:
            job_states = states_by_batch.get(rec.id, set())
            if (state := rec._get_state(job_states)) != rec.state:
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
        grouped = self.env["queue.job"].read_group(
            [("job_batch_id", "in", self.ids)],
            ["job_batch_id", "state"],
            ["job_batch_id", "state"],
            lazy=False,
        )
        counts = {}
        for g in grouped:
            batch_id = g["job_batch_id"][0]
            counts.setdefault(batch_id, {})
            counts[batch_id][g["state"]] = g["__count"]

        for rec in self:
            by_state = counts.get(rec.id, {})
            total = sum(by_state.values())
            done = by_state.get("done", 0)
            failed = by_state.get("failed", 0)

            rec.job_count = total
            rec.failed_job_count = failed
            rec.finished_job_count = done
            rec.completeness = done / max(1, total)
            rec.failed_percentage = failed / max(1, total)

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
