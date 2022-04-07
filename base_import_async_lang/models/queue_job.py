# Copyright 2022 Ooops (https://ooops404.com).
# @author Ashish Hirpara <hello@ashish-hirpara.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class QueueJob(models.Model):
    _inherit = "queue.job"

    lang_id = fields.Many2one("res.lang", "Language")

    @api.model_create_multi
    def create(self, vals_list):
        res = super(QueueJob, self).create(vals_list)
        job_uuid = "job_uuid" in self._context and self._context["job_uuid"] or ""
        job = self.search([("uuid", "=", job_uuid)], limit=1)
        if job and job.lang_id:
            res.lang_id = job.lang_id.id
        else:
            res.lang_id = (
                self.env["res.lang"]
                .search(
                    [("code", "=", self.env.user.lang)],
                    limit=1,
                )
                .id
            )
        return res
