# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import json
import operator
import base64
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.addons.queue_job.job import job
from odoo.addons.web.controllers.main import CSVExport, ExcelExport
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DelayExport(models.Model):

    _name = 'delay.export'
    _description = 'Allow to delay the export'

    user_id = fields.Many2one('res.users', string='User', index=True)

    @api.model
    def delay_export(self, data):
        params = json.loads(data.get('data'))
        if not self.env.user.email:
            raise UserError(_("You must set an email address to your user."))
        self.with_delay().export(params)

    @api.model
    def _get_file_content(self, params):
        export_format = params.get('format')
        raw_data = export_format != 'csv'

        model_name, fields_name, ids, domain, import_compat, context = \
            operator.itemgetter('model', 'fields', 'ids',
                                'domain', 'import_compat', 'context')(params)
        user = self.env['res.users'].browse([context.get('uid')])
        if not user or not user.email:
            raise UserError(_("The user doesn't have an email address."))

        model = self.env[model_name].with_context(
            import_compat=import_compat, **context)
        records = model.browse(ids) or model.search(
            domain, offset=0, limit=False, order=False)

        if not model._is_an_ordinary_table():
            fields_name = [field for field in fields_name
                           if field['name'] != 'id']

        field_names = [f['name'] for f in fields_name]
        import_data = records.export_data(
            field_names, raw_data).get('datas', [])

        if import_compat:
            columns_headers = field_names
        else:
            columns_headers = [val['label'].strip() for val in fields_name]

        if export_format == 'csv':
            csv = CSVExport()
            return csv.from_data(columns_headers, import_data)
        else:
            xls = ExcelExport()
            return xls.from_data(columns_headers, import_data)

    @api.model
    @job
    def export(self, params):
        content = self._get_file_content(params)

        model_name, context, export_format = \
            operator.itemgetter('model', 'context', 'format')(params)
        user = self.env['res.users'].browse([context.get('uid')])

        export_record = self.sudo().create({'user_id': user.id})

        name = "{}.{}".format(model_name, export_format)
        attachment = self.env['ir.attachment'].create({
            'name': name,
            'datas': base64.b64encode(content),
            'datas_fname': name,
            'type': 'binary',
            'res_model': self._name,
            'res_id': export_record.id,
        })

        url = "{}/web/content/ir.attachment/{}/datas/{}?download=true".format(
            self.env['ir.config_parameter'].sudo().get_param('web.base.url'),
            attachment.id,
            attachment.name,
        )

        time_to_live = self.env['ir.config_parameter'].sudo(). \
            get_param('attachment.ttl', 7)
        date_today = fields.Date.today()
        expiration_date = fields.Date.to_string(
            date_today + relativedelta(days=+int(time_to_live)))

        # TODO : move to email template
        odoo_bot = self.sudo().env.ref("base.partner_root")
        email_from = odoo_bot.email
        model_description = self.env[model_name]._description
        self.env['mail.mail'].create({
            'email_from': email_from,
            'reply_to': email_from,
            'email_to': user.email,
            'subject': _("Export {} {}").format(
                model_description, fields.Date.to_string(fields.Date.today())),
            'body_html': _("""
                <p>Your export is available <a href="{}">here</a>.</p>
                <p>It will be automatically deleted the {}.</p>
                <p>&nbsp;</p>
                <p><span style="color: #808080;">
                This is an automated message please do not reply.
                </span></p>
                """).format(url, expiration_date),
            'auto_delete': True,
        })

    @api.model
    def cron_delete(self):
        time_to_live = self.env['ir.config_parameter'].sudo(). \
            get_param('attachment.ttl', 7)
        date_today = fields.Date.today()
        date_to_delete = date_today + relativedelta(days=-int(time_to_live))
        self.search([('create_date', '<=', date_to_delete)]).unlink()
