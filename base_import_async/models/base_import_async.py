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

from openerp.models import TransientModel
from openerp.models import fix_import_export_id_paths
from openerp.tools.translate import _

from openerp.addons.connector.queue.job import job, related_action
from openerp.addons.connector.session import ConnectorSession
from openerp.addons.connector.exception import FailedJobError

# options defined in base_import/import.js
OPT_HAS_HEADER = 'headers'
OPT_SEPARATOR = 'separator'
OPT_QUOTING = 'quoting'
OPT_ENCODING = 'encoding'
# options defined in base_import_async/import.js
OPT_USE_CONNECTOR = 'use_connector'
OPT_CHUNK_SIZE = 'chunk_size'
# option not available in UI, but usable from scripts
OPT_PRIORITY = 'priority'

INIT_PRIORITY = 100
DEFAULT_CHUNK_SIZE = 100


def _encode(row, encoding):
    return [cell.encode(encoding) for cell in row]


def _decode(row, encoding):
    return [cell.decode(encoding) for cell in row]


def _create_csv_attachment(session, fields, data, options, file_name):
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
    attachment = session.env['ir.attachment'].create({
        'name': file_name,
        'datas': f.getvalue().encode('base64')
    })
    return attachment.id


def _read_csv_attachment(session, att_id, options):
    att = session.env['ir.attachment'].browse(att_id)
    f = StringIO(att.datas.decode('base64'))
    reader = csv.reader(f,
                        delimiter=str(options.get(OPT_SEPARATOR)),
                        quotechar=str(options.get(OPT_QUOTING)))
    encoding = options.get(OPT_ENCODING, 'utf-8')
    fields = _decode(reader.next(), encoding)
    data = [_decode(row, encoding) for row in reader]
    return fields, data


def _link_attachment_to_job(session, job_uuid, att_id):
    job = session.env['queue.job'].search([('uuid', '=', job_uuid)], limit=1)
    session.env['ir.attachment'].browse(att_id).write({
        'res_model': 'queue.job',
        'res_id': job.id,
    })


def _extract_records(session, model_obj, fields, data, chunk_size):
    """ Split the data on record boundaries,
    in chunks of minimum chunk_size """
    fields = map(fix_import_export_id_paths, fields)
    row_from = 0
    for rows in model_obj._extract_records(session.cr,
                                           session.uid,
                                           fields,
                                           data,
                                           context=session.context):
        rows = rows[1]['rows']
        if rows['to'] - row_from + 1 >= chunk_size:
            yield row_from, rows['to']
            row_from = rows['to'] + 1
    if row_from < len(data):
        yield row_from, len(data) - 1


def related_attachment(session, thejob):
    attachment_id = thejob.args[1]

    action = {
        'name': _("Attachment"),
        'type': 'ir.actions.act_window',
        'res_model': "ir.attachment",
        'view_type': 'form',
        'view_mode': 'form',
        'res_id': attachment_id,
    }
    return action


@job
@related_action(action=related_attachment)
def import_one_chunk(session, res_model, att_id, options):
    model_obj = session.pool[res_model]
    fields, data = _read_csv_attachment(session, att_id, options)
    result = model_obj.load(session.cr,
                            session.uid,
                            fields,
                            data,
                            context=session.context)
    error_message = [message['message'] for message in result['messages']
                     if message['type'] == 'error']
    if error_message:
        raise FailedJobError('\n'.join(error_message))
    return result


@job
def split_file(session, model_name, translated_model_name,
               att_id, options, file_name="file.csv"):
    """ Split a CSV attachment in smaller import jobs """
    model_obj = session.pool[model_name]
    fields, data = _read_csv_attachment(session, att_id, options)
    padding = len(str(len(data)))
    priority = options.get(OPT_PRIORITY, INIT_PRIORITY)
    if options.get(OPT_HAS_HEADER):
        header_offset = 1
    else:
        header_offset = 0
    chunk_size = options.get(OPT_CHUNK_SIZE) or DEFAULT_CHUNK_SIZE
    for row_from, row_to in _extract_records(session,
                                             model_obj,
                                             fields,
                                             data,
                                             chunk_size):
        chunk = str(priority - INIT_PRIORITY).zfill(padding)
        description = _("Import %s from file %s - #%s - lines %s to %s") % \
            (translated_model_name,
             file_name,
             chunk,
             row_from + 1 + header_offset,
             row_to + 1 + header_offset)
        # create a CSV attachment and enqueue the job
        root, ext = os.path.splitext(file_name)
        att_id = _create_csv_attachment(session,
                                        fields,
                                        data[row_from:row_to + 1],
                                        options,
                                        file_name=root + '-' + chunk + ext)
        job_uuid = import_one_chunk.delay(session,
                                          model_name,
                                          att_id,
                                          options,
                                          description=description,
                                          priority=priority)
        _link_attachment_to_job(session, job_uuid, att_id)
        priority += 1


class BaseImportConnector(TransientModel):
    _inherit = 'base_import.import'

    def do(self, cr, uid, res_id, fields, options, dryrun=False, context=None):
        if dryrun or not options.get(OPT_USE_CONNECTOR):
            # normal import
            return super(BaseImportConnector, self).do(
                cr, uid, res_id, fields, options, dryrun=dryrun,
                context=context)

        # asynchronous import
        (record,) = self.browse(cr, uid, [res_id], context=context)
        try:
            data, import_fields = self._convert_import_data(
                record, fields, options, context=context)
        except ValueError, e:
            return [{
                'type': 'error',
                'message': unicode(e),
                'record': False,
            }]

        # get the translated model name to build
        # a meaningful job description
        search_result = self.pool['ir.model'].name_search(
            cr, uid, args=[('model', '=', record.res_model)], context=context)
        if search_result:
            translated_model_name = search_result[0][1]
        else:
            translated_model_name = self.pool[record.res_model]._description
        description = _("Import %s from file %s") % \
            (translated_model_name, record.file_name)

        # create a CSV attachment and enqueue the job
        session = ConnectorSession(cr, uid, context)
        att_id = _create_csv_attachment(session,
                                        import_fields,
                                        data,
                                        options,
                                        record.file_name)
        job_uuid = split_file.delay(session,
                                    record.res_model,
                                    translated_model_name,
                                    att_id,
                                    options,
                                    file_name=record.file_name,
                                    description=description)
        _link_attachment_to_job(session, job_uuid, att_id)

        return []
