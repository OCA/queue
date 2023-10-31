# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import json
import operator

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.web.controllers.main import CSVExport, ExcelExport


class DelayExport(models.Model):

    _name = "delay.export"
    _description = "Asynchronous Export"

    user_ids = fields.Many2many("res.users", string="Users", index=True)
    model_description = fields.Char()
    url = fields.Char()
    expiration_date = fields.Date()

    @api.model
    def delay_export(self, data):
        """Delay the export, called from js"""
        params = json.loads(data.get("data"))
        if not self.env.user.email:
            raise UserError(_("You must set an email address to your user."))
        self.with_delay().export(params)

    @api.model
    def _get_file_content(self, params):
        export_format = params.get("format")

        items = operator.itemgetter(
            "model", "fields", "ids", "domain", "import_compat", "context", "user_ids"
        )(params)
        (model_name, fields_name, ids, domain, import_compat, context, user_ids) = items

        model = self.env[model_name].with_context(
            import_compat=import_compat, **context
        )
        records = model.browse(ids) or model.search(
            domain, offset=0, limit=False, order=False
        )

        if not model._is_an_ordinary_table():
            fields_name = [field for field in fields_name if field["name"] != "id"]

        field_names = [f["name"] for f in fields_name]
        import_data = records.export_data(field_names).get("datas", [])

        if import_compat:
            columns_headers = field_names
        else:
            columns_headers = [val["label"].strip() for val in fields_name]

        if export_format == "csv":
            csv = CSVExport()
            return csv.from_data(columns_headers, import_data)
        else:
            xls = ExcelExport()
            return xls.from_data(columns_headers, import_data)

    @api.model
    def export(self, params):
        """Delayed export of a file sent by email

        The ``params`` is a dict of parameters, contains:

        * format: csv/excel
        * model: model to export
        * fields: list of fields to export, a list of dict:
          [{'label': '', 'name': ''}]
        * ids: list of ids to export
        * domain: domain for the export
        * context: context for the export (language, ...)
        * import_compat: if the export is export/import compatible (boolean)
        * user_ids: optional list of user ids who receive the file
        """
        content = self._get_file_content(params)

        items = operator.itemgetter("model", "context", "format", "user_ids")(params)
        model_name, context, export_format, user_ids = items
        users = self.env["res.users"].browse(user_ids)

        export_record = self.sudo().create({"user_ids": [(6, 0, users.ids)]})

        name = "{}.{}".format(model_name, export_format)
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": name,
                    "datas": base64.b64encode(content),
                    "type": "binary",
                    "res_model": self._name,
                    "res_id": export_record.id,
                }
            )
        )

        url = "{}/web/content/ir.attachment/{}/datas/{}?download=true".format(
            self.env["ir.config_parameter"].sudo().get_param("web.base.url"),
            attachment.id,
            attachment.name,
        )

        time_to_live = (
            self.env["ir.config_parameter"].sudo().get_param("attachment.ttl", 7)
        )
        date_today = fields.Date.today()
        expiration_date = fields.Date.to_string(
            date_today + relativedelta(days=+int(time_to_live))
        )

        odoo_bot = self.sudo().env.ref("base.partner_root")
        email_from = odoo_bot.email
        model_description = self.env[model_name]._description
        export_record.write(
            {
                "url": url,
                "expiration_date": expiration_date,
                "model_description": model_description,
            }
        )

        self.env.ref("base_export_async.delay_export_mail_template").send_mail(
            export_record.id,
            email_values={
                "email_from": email_from,
                "reply_to": email_from,
                "recipient_ids": [(6, 0, users.mapped("partner_id").ids)],
            },
        )

    @api.model
    def cron_delete(self):
        time_to_live = (
            self.env["ir.config_parameter"].sudo().get_param("attachment.ttl", 7)
        )
        date_today = fields.Date.today()
        date_to_delete = date_today + relativedelta(days=-int(time_to_live))
        self.search([("create_date", "<=", date_to_delete)]).unlink()
