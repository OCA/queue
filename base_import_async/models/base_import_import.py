# -*- coding: utf-8 -*-
###############################################################################
#
#   Module for Odoo
#   Copyright (C) 2014 ACSONE SA/NV (http://acsone.eu).
#   Copyright (C) 2013 Akretion (http://www.akretion.com).
#   @author Stéphane Bidoul <stephane.bidoul@acsone.eu>
#   @author Sébastien BEAU <sebastien.beau@akretion.com>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import csv
import os
from cStringIO import StringIO

from odoo import api, _
from odoo.models import TransientModel
from odoo.models import fix_import_export_id_paths

from odoo.addons.queue_job.job import job, related_action
from odoo.addons.queue_job.exception import FailedJobError

# options defined in base_import/import.js
OPT_HAS_HEADER = 'headers'
OPT_SEPARATOR = 'separator'
OPT_QUOTING = 'quoting'
OPT_ENCODING = 'encoding'
# options defined in base_import_async/import.js
OPT_USE_QUEUE = 'use_queue'
OPT_CHUNK_SIZE = 'chunk_size'
# option not available in UI, but usable from scripts
OPT_PRIORITY = 'priority'

INIT_PRIORITY = 100
DEFAULT_CHUNK_SIZE = 100


def _encode(row, encoding):
    return [cell.encode(encoding) for cell in row]


def _decode(row, encoding):
    return [cell.decode(encoding) for cell in row]


class BaseImportImport(TransientModel):
    _inherit = 'base_import.import'

    @api.multi
    def do(self, fields, options, dryrun=False):
        if dryrun or not options.get(OPT_USE_QUEUE):
            # normal import
            return super(BaseImportImport, self).do(
                fields, options, dryrun=dryrun)

        # asynchronous import
        try:
            data, import_fields = self._convert_import_data(fields, options)
            # Parse date and float field
            data = self._parse_import_data(data, import_fields, options)
        except ValueError as e:
            return [{
                'type': 'error',
                'message': unicode(e),
                'record': False,
            }]

        # get the translated model name to build
        # a meaningful job description
        search_result = self.env['ir.model'].name_search(
            self.res_model, operator='=')
        if search_result:
            translated_model_name = search_result[0][1]
        else:
            translated_model_name = self._description
        description = _("Import %s from file %s") % \
            (translated_model_name, self.file_name)
        att_id = self._create_csv_attachment(
            import_fields, data, options, self.file_name)
        job_uuid = self.with_delay(description=description)._split_file(
            model_name=self.res_model,
            translated_model_name=translated_model_name,
            att_id=att_id,
            options=options,
            file_name=self.file_name
        )
        self._link_attachment_to_job(job_uuid, att_id)
        return []

    @api.model
    def _link_attachment_to_job(self, job_uuid, att_id):
        job = self.env['queue.job'].search([('uuid', '=', job_uuid)], limit=1)
        self.env['ir.attachment'].browse(att_id).write({
            'res_model': 'queue.job',
            'res_id': job.id,
        })

    @api.model
    def _create_csv_attachment(self, fields, data, options, file_name):
        # write csv
        f = StringIO()
        writer = csv.writer(f,
                            delimiter=str(options.get(OPT_SEPARATOR)),
                            quotechar=str(options.get(OPT_QUOTING)))
        encoding = options.get(OPT_ENCODING, 'utf-8')
        writer.writerow(_encode(fields, encoding))
        for row in data:
            writer.writerow(_encode(row, encoding))
        # create attachment
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'datas': f.getvalue().encode('base64'),
            'datas_fname': file_name
        })
        return attachment.id

    @api.model
    def _read_csv_attachment(self, att_id, options):
        att = self.env['ir.attachment'].browse(att_id)
        f = StringIO(att.datas.decode('base64'))
        reader = csv.reader(f,
                            delimiter=str(options.get(OPT_SEPARATOR)),
                            quotechar=str(options.get(OPT_QUOTING)))
        encoding = options.get(OPT_ENCODING, 'utf-8')
        fields = _decode(reader.next(), encoding)
        data = [_decode(row, encoding) for row in reader]
        return fields, data

    @api.model
    def _extract_records(self, model_obj, fields, data, chunk_size):
        """ Split the data on record boundaries,
        in chunks of minimum chunk_size """
        fields = map(fix_import_export_id_paths, fields)
        row_from = 0
        for rows in model_obj._extract_records(fields,
                                               data):
            rows = rows[1]['rows']
            if rows['to'] - row_from + 1 >= chunk_size:
                yield row_from, rows['to']
                row_from = rows['to'] + 1
        if row_from < len(data):
            yield row_from, len(data) - 1

    @api.model
    @job
    @related_action('_related_action_attachment')
    def _split_file(self, model_name, translated_model_name,
                    att_id, options, file_name="file.csv"):
        """ Split a CSV attachment in smaller import jobs """
        model_obj = self.env[model_name]
        fields, data = self._read_csv_attachment(att_id, options)
        padding = len(str(len(data)))
        priority = options.get(OPT_PRIORITY, INIT_PRIORITY)
        if options.get(OPT_HAS_HEADER):
            header_offset = 1
        else:
            header_offset = 0
        chunk_size = options.get(OPT_CHUNK_SIZE) or DEFAULT_CHUNK_SIZE
        for row_from, row_to in self._extract_records(
                model_obj, fields, data, chunk_size):
            chunk = str(priority - INIT_PRIORITY).zfill(padding)
            description = _("Import %s from file %s - #%s - lines %s to %s")
            description = description % (translated_model_name,
                                         file_name,
                                         chunk,
                                         row_from + 1 + header_offset,
                                         row_to + 1 + header_offset)
            # create a CSV attachment and enqueue the job
            root, ext = os.path.splitext(file_name)
            att_id = self._create_csv_attachment(
                fields, data[row_from:row_to + 1], options,
                file_name=root + '-' + chunk + ext)
            job_uuid = self.with_delay(
                description=description, priority=priority)._import_one_chunk(
                    model_name=model_name,
                    att_id=att_id,
                    options=options)
            self._link_attachment_to_job(job_uuid, att_id)
            priority += 1

    @api.model
    @job
    @related_action('_related_action_attachment')
    def _import_one_chunk(self, model_name, att_id, options):
        model_obj = self.env[model_name]
        fields, data = self._read_csv_attachment(att_id, options)
        result = model_obj.load(fields, data)
        error_message = [message['message'] for message in result['messages']
                         if message['type'] == 'error']
        if error_message:
            raise FailedJobError('\n'.join(error_message))
        return result
