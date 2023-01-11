# Copyright 2019 Camptocamp
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

from odoo.addons.base.models.res_partner import _lang_get


class ExportAsyncSchedule(models.Model):
    _name = "export.async.schedule"
    _description = "Export Async Schedule"

    active = fields.Boolean(default=True)

    # Export configuration
    model_id = fields.Many2one(
        comodel_name="ir.model", required=True, ondelete="cascade"
    )
    model_name = fields.Char(related="model_id.model", string="Model Name")
    user_ids = fields.Many2many(
        string="Recipients", comodel_name="res.users", required=True
    )
    domain = fields.Char(string="Export Domain", default=[])
    ir_export_id = fields.Many2one(
        comodel_name="ir.exports",
        string="Export List",
        required=True,
        domain="[('resource', '=', model_name)]",
        ondelete="restrict",
    )
    export_format = fields.Selection(
        selection=[("csv", "CSV"), ("excel", "Excel")],
        default="csv",
        required=True,
    )
    import_compat = fields.Boolean(string="Import-compatible Export")
    lang = fields.Selection(
        _lang_get,
        string="Language",
        default=lambda self: self.env.lang,
        help="Exports will be translated in this language.",
    )

    # Scheduling
    next_execution = fields.Datetime(default=fields.Datetime.now, required=True)
    interval = fields.Integer(default=1, required=True)
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
    )
    end_of_month = fields.Boolean()

    def name_get(self):
        result = []
        for record in self:
            name = "{}: {}".format(record.model_id.name, record.ir_export_id.name)
            result.append((record.id, name))
        return result

    def run_schedule(self):
        for record in self:
            if record.next_execution > datetime.now():
                continue
            record.action_export()
            record.next_execution = record._compute_next_date()

    def _compute_next_date(self):
        next_execution = self.next_execution
        if next_execution < datetime.now():
            next_execution = datetime.now()
        args = {self.interval_unit: self.interval}
        if self.interval_unit == "months" and self.end_of_month:
            # dateutil knows how to deal with variable days of months,
            # it will put the latest possible day
            args.update({"day": 31, "hour": 23, "minute": 59, "second": 59})
        return next_execution + relativedelta(**args)

    @api.onchange("end_of_month")
    def onchange_end_of_month(self):
        if self.end_of_month:
            self.next_execution = self.next_execution + relativedelta(
                day=31, hour=23, minute=59, second=59
            )

    @api.model
    def _get_fields_with_labels(self, model_name, export_fields):
        self_fields = self.env[model_name]._fields
        result = []
        for field_name in export_fields:
            if "/" in field_name:
                # The ir.exports.line model contains only the name of the
                # field, and when we follow relations, the name of the fields
                # joined by /. example: 'bank_ids/acc_number'
                # Here, we follow the relations to get the labels
                parts = field_name.split("/")
                model_fields = self_fields
                label_parts = []
                for cur_field_name in parts:
                    cur_field = model_fields[cur_field_name]
                    label_parts.append(cur_field._description_string(self.env))
                    comodel_name = cur_field.comodel_name
                    if comodel_name:
                        model_fields = self.env[cur_field.comodel_name]._fields
                label = "/".join(label_parts)
            else:
                label = self_fields[field_name]._description_string(self.env)
            result.append({"label": label, "name": field_name})
        return result

    def _prepare_export_params(self):
        export_fields = [
            export_field.name for export_field in self.ir_export_id.export_fields
        ]
        if self.import_compat:
            export_fields = [
                {"label": export_field, "name": export_field}
                for export_field in export_fields
            ]
        else:
            export_fields = self._get_fields_with_labels(
                self.model_name,
                [export_field for export_field in export_fields],
            )
        export_format = self.export_format == "excel" and "xlsx" or self.export_format
        return {
            "format": export_format,
            "model": self.model_name,
            "fields": export_fields,
            "ids": False,
            "domain": safe_eval(self.domain),
            "context": self.env.context,
            "import_compat": self.import_compat,
            "user_ids": self.user_ids.ids,
        }

    def action_export(self):
        for record in self:
            record = record.with_context(lang=record.lang)
            params = record._prepare_export_params()
            record.env["delay.export"].with_delay().export(params)
