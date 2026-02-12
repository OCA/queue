# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, exceptions, fields, models


class QueueJobFunction(models.Model):
    _inherit = "queue.job.function"

    profiling_enabled = fields.Boolean(
        string="Profiling enabled",
        help="Indicates whether profiling is enabled for this job function.",
    )
    profiling_user_ids = fields.Many2many(
        "res.users",
        string="Profiling users",
        help="The users allowed to perform profiling for this job function.",
    )
    profiling_until = fields.Datetime(
        string="Profiling until",
        help="The date and time until which profiling is enabled "
        "for this job function.",
    )

    def is_profiling_enabled(self):
        self.ensure_one()
        return (
            self.profiling_enabled
            and (self.profiling_until and self.profiling_until >= fields.Datetime.now())
            and (
                not self.profiling_user_ids or self.env.user in self.profiling_user_ids
            )
        )

    @api.constrains("profiling_enabled")
    def _check_profiling_setup(self):
        for record in self:
            if record.profiling_enabled and not record.profiling_until:
                raise exceptions.ValidationError(
                    self.env._(
                        "A profiling until date must be set when profiling is enabled."
                    )
                )

    def _profile_make_name(self, job):
        self.ensure_one()
        return f"queue.job {job.uuid} - {self.name}"
