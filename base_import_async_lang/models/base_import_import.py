# Copyright 2022 Ooops (https://ooops404.com).
# @author Ashish Hirpara <hello@ashish-hirpara.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models

from odoo.addons.queue_job.exception import FailedJobError


class BaseImportImport(models.TransientModel):
    _inherit = "base_import.import"

    def _import_one_chunk(self, model_name, attachment, options):
        model_obj = self.env[model_name]
        fields, data = self._read_csv_attachment(attachment, options)
        job_uuid = "job_uuid" in self._context and self._context["job_uuid"] or ""
        lang = self.env["queue.job"].search([("uuid", "=", job_uuid)], limit=1).lang_id
        if lang:
            result = model_obj.with_context(lang=lang.code).load(fields, data)
        else:
            result = model_obj.load(fields, data)
        error_message = [
            message["message"]
            for message in result["messages"]
            if message["type"] == "error"
        ]
        if error_message:
            raise FailedJobError("\n".join(error_message))
        return result
