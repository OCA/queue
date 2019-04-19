# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import json
import operator
import base64

from odoo import api, fields, models, _
from odoo.addons.queue_job.job import job
from odoo.addons.web.controllers.main import CSVExport, ExcelExport
from odoo.exceptions import Warning

_logger = logging.getLogger(__name__)


class DelayExport(models.Model):

    _name = 'delay.export'
    _description = 'Allow to delay the export'

    @api.model
    def delay_export(self, data):
        params = json.loads(data.get('data'))
        context = params.get('context', {})
        uid = context.get('uid', False)
        if not uid:
            raise Warning(_("A problem occurs during the job creation. Please contact your administrator"))
        user = self.env['res.users'].browse([uid])
        if not user.email:
            raise Warning(_("You must set an email address to your user."))
        self.with_delay().export(params)

    @api.model
    @job
    def export(self, params):
        export_format = params.get('format')
        raw_data = export_format != 'csv'

        model_name, fields_name, ids, domain, import_compat, context = \
            operator.itemgetter('model', 'fields', 'ids', 'domain', 'import_compat', 'context')(params)
        user = self.env['res.users'].browse([context.get('uid')])
        if not user or not user.email:
            raise Warning(_("The user doesn't have an email address."))

        model = self.env[model_name].with_context(import_compat=import_compat, **context)
        records = model.browse(ids) or model.search(domain, offset=0, limit=False, order=False)

        if not model._is_an_ordinary_table():
            fields_name = [field for field in fields_name if field['name'] != 'id']

        field_names = [f['name'] for f in fields_name]
        import_data = records.export_data(field_names, raw_data).get('datas', [])

        if import_compat:
            columns_headers = field_names
        else:
            columns_headers = [val['label'].strip() for val in fields_name]

        if export_format == 'csv':
            csv = CSVExport()
            result = csv.from_data(columns_headers, import_data)
        else:
            xls = ExcelExport()
            result = xls.from_data(columns_headers, import_data)

        attachment = self.env['ir.attachment'].create({
            'name': "{}.{}".format(model_name, export_format),
            'datas': base64.b64encode(result),
            'datas_fname': "{}.{}".format(model_name, export_format),
            'type': 'binary'
        })

        odoobot = self.env.ref("base.partner_root")
        email_from = odoobot.email
        self.env['mail.mail'].create({
            'email_from': email_from,
            'reply_to': email_from,
            'email_to': user.email,
            'subject': _("Export {} {}").format(model_name,
                fields.Date.to_string(fields.Date.today())),
            'body_html': _("This is an automated message please do not reply."),
            'attachment_ids': [(4, attachment.id)],
            'auto_delete': True,
        })
