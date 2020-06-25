# Copyright 2014 ACSONE SA/NV (http://acsone.eu).
# Copyright 2013 Akretion (http://www.akretion.com).
# @author Stéphane Bidoul <stephane.bidoul@acsone.eu>
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import csv
from io import BytesIO, StringIO, TextIOWrapper
from os.path import splitext

from odoo import _, api, models
from odoo.models import fix_import_export_id_paths

from odoo.addons.queue_job.exception import FailedJobError
from odoo.addons.queue_job.job import job, related_action

# options defined in base_import/import.js
OPT_HAS_HEADER = "headers"
OPT_SEPARATOR = "separator"
OPT_QUOTING = "quoting"
OPT_ENCODING = "encoding"
# options defined in base_import_async/import.js
OPT_USE_QUEUE = "use_queue"
OPT_CHUNK_SIZE = "chunk_size"
# option not available in UI, but usable from scripts
OPT_PRIORITY = "priority"

INIT_PRIORITY = 100
DEFAULT_CHUNK_SIZE = 100


class BaseImportImport(models.TransientModel):
    _inherit = "base_import.import"

    def do(self, fields, columns, options, dryrun=False):
        if dryrun or not options.get(OPT_USE_QUEUE):
            # normal import
            return super().do(fields, columns, options, dryrun=dryrun)

        # asynchronous import
        try:
            data, import_fields = self._convert_import_data(fields, options)
            # Parse date and float field
            data = self._parse_import_data(data, import_fields, options)
        except ValueError as e:
            return {"messages": [{"type": "error", "message": str(e), "record": False}]}

        # get the translated model name to build
        # a meaningful job description
        search_result = self.env["ir.model"].name_search(self.res_model, operator="=")
        if search_result:
            translated_model_name = search_result[0][1]
        else:
            translated_model_name = self._description
        description = _("Import %s from file %s") % (
            translated_model_name,
            self.file_name,
        )
        attachment = self._create_csv_attachment(
            import_fields, data, options, self.file_name
        )
        delayed_job = self.with_delay(description=description)._split_file(
            model_name=self.res_model,
            translated_model_name=translated_model_name,
            attachment=attachment,
            options=options,
            file_name=self.file_name,
        )
        self._link_attachment_to_job(delayed_job, attachment)
        return []

    def _link_attachment_to_job(self, delayed_job, attachment):
        queue_job = self.env["queue.job"].search(
            [("uuid", "=", delayed_job.uuid)], limit=1
        )
        attachment.write({"res_model": "queue.job", "res_id": queue_job.id})

    @api.returns("ir.attachment")
    def _create_csv_attachment(self, fields, data, options, file_name):
        # write csv
        f = StringIO()
        writer = csv.writer(
            f,
            delimiter=str(options.get(OPT_SEPARATOR)) or ",",
            quotechar=str(options.get(OPT_QUOTING)),
        )
        encoding = options.get(OPT_ENCODING) or "utf-8"
        writer.writerow(fields)
        for row in data:
            writer.writerow(row)
        # create attachment
        datas = base64.encodebytes(f.getvalue().encode(encoding))
        attachment = self.env["ir.attachment"].create(
            {"name": file_name, "datas": datas}
        )
        return attachment

    def _read_csv_attachment(self, attachment, options):
        decoded_datas = base64.decodebytes(attachment.datas)
        encoding = options.get(OPT_ENCODING) or "utf-8"
        f = TextIOWrapper(BytesIO(decoded_datas), encoding=encoding)
        reader = csv.reader(
            f,
            delimiter=str(options.get(OPT_SEPARATOR)) or ",",
            quotechar=str(options.get(OPT_QUOTING)),
        )

        fields = next(reader)
        data = [row for row in reader]
        return fields, data

    @staticmethod
    def _extract_chunks(model_obj, fields, data, chunk_size):
        """ Split the data on record boundaries,
        in chunks of minimum chunk_size """
        fields = list(map(fix_import_export_id_paths, fields))
        row_from = 0
        for rows in model_obj._extract_records(fields, data):
            rows = rows[1]["rows"]
            if rows["to"] - row_from + 1 >= chunk_size:
                yield row_from, rows["to"]
                row_from = rows["to"] + 1
        if row_from < len(data):
            yield row_from, len(data) - 1

    @job
    @related_action("_related_action_attachment")
    def _split_file(
        self,
        model_name,
        translated_model_name,
        attachment,
        options,
        file_name="file.csv",
    ):
        """ Split a CSV attachment in smaller import jobs """
        model_obj = self.env[model_name]
        fields, data = self._read_csv_attachment(attachment, options)
        padding = len(str(len(data)))
        priority = options.get(OPT_PRIORITY, INIT_PRIORITY)
        if options.get(OPT_HAS_HEADER):
            header_offset = 1
        else:
            header_offset = 0
        chunk_size = options.get(OPT_CHUNK_SIZE) or DEFAULT_CHUNK_SIZE
        for row_from, row_to in self._extract_chunks(
            model_obj, fields, data, chunk_size
        ):
            chunk = str(priority - INIT_PRIORITY).zfill(padding)
            description = _("Import %s from file %s - #%s - lines %s to %s")
            description = description % (
                translated_model_name,
                file_name,
                chunk,
                row_from + 1 + header_offset,
                row_to + 1 + header_offset,
            )
            # create a CSV attachment and enqueue the job
            root, ext = splitext(file_name)
            attachment = self._create_csv_attachment(
                fields,
                data[row_from : row_to + 1],
                options,
                file_name=root + "-" + chunk + ext,
            )
            delayed_job = self.with_delay(
                description=description, priority=priority
            )._import_one_chunk(
                model_name=model_name, attachment=attachment, options=options
            )
            self._link_attachment_to_job(delayed_job, attachment)
            priority += 1

    @job
    @related_action("_related_action_attachment")
    def _import_one_chunk(self, model_name, attachment, options):
        model_obj = self.env[model_name]
        fields, data = self._read_csv_attachment(attachment, options)
        result = model_obj.load(fields, data)
        error_message = [
            message["message"]
            for message in result["messages"]
            if message["type"] == "error"
        ]
        if error_message:
            raise FailedJobError("\n".join(error_message))
        return result
