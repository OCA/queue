# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from odoo.addons.base.models.res_partner import _lang_get


class ExportAsyncScheduleMixin(models.AbstractModel):
    _name = "export.async.schedule.mixin"
    _description = "Export Async Schedule Mixin"

    active = fields.Boolean(default=True)
    user_ids = fields.Many2many(
        string="Recipients",
        comodel_name="res.users",
    )

    next_execution = fields.Datetime(
        default=fields.Datetime.now, required=True, tracking=True, copy=False
    )
    interval = fields.Integer(default=1, required=True, tracking=True)
    interval_unit = fields.Selection(
        selection=[
            ("hours", "Hour(s)"),
            ("days", "Day(s)"),
            ("weeks", "Week(s)"),
            ("months", "Month(s)"),
        ],
        string="Unit",
        default="months",
        required=True,
        tracking=True,
    )
    end_of_month = fields.Boolean(tracking=True)
    lang = fields.Selection(
        _lang_get,
        string="Language",
        default=lambda self: self.env.lang,
        help="Exports will be translated in this language.",
        tracking=True,
    )

    def _compute_next_date(self):
        self.ensure_one()
        next_execution = self.next_execution
        if next_execution < datetime.now():
            next_execution = datetime.now()
        return next_execution + relativedelta(**self._get_next_date_args())

    def _get_next_date_args(self):
        """Return the arguments for relativedelta. Override to customize."""
        args = {self.interval_unit: self.interval}
        if self.interval_unit == "months" and self.end_of_month:
            args.update({"day": 31, "hour": 23, "minute": 59, "second": 59})
        return args

    def _get_recipient_emails(self):
        """Return comma-separated email addresses of recipients with valid emails."""
        self.ensure_one()
        return ",".join(self.user_ids.filtered("email").mapped("email"))

    @api.onchange("end_of_month")
    def _onchange_end_of_month(self):
        if self.end_of_month:
            self.next_execution = self.next_execution + relativedelta(
                day=31, hour=23, minute=59, second=59
            )
