# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class QueueJob(models.Model):
    _inherit = "queue.job"

    job_is_profiled = fields.Boolean(
        string="Profiled",
        default=False,
        help="Whether this job has been profiled or not.",
        compute="_compute_job_is_profiled",
        compute_sudo=True,
    )

    @api.depends("job_function_id")
    def _compute_job_is_profiled(self):
        for job in self:
            if not job.job_function_id:
                # cannot be profiled if it has no function
                job.job_is_profiled = False
                continue
            profile_name = job.job_function_id._profile_make_name(job)
            job.job_is_profiled = bool(job._profiler_get_record(profile_name))

    def _profiler_get_record(self, profile_name):
        # don't care about perf as this is loaded only on the job form view
        IrProfile = self.env["ir.profile"].sudo()
        return IrProfile.search(
            [("name", "=", profile_name)],
            limit=1,
        )

    def action_view_profile(self):
        self.ensure_one()
        if not self.job_function_id:
            return {"type": "ir.actions.act_window_close"}
        profile_name = self.job_function_id._profile_make_name(self)
        profile = self._profiler_get_record(profile_name)
        if not profile:
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "name": "Profile",
            "res_model": "ir.profile",
            "view_mode": "form",
            "res_id": profile.id,
            "target": "current",
        }
