# Copyright 2026 Ecosoft Co., Ltd. (https://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from lxml import etree

from odoo import api, fields, models
from odoo.tools import SQL

from .constants import JOB_RECORD_IDS_SQL, RUNNING_STATES


class QueueJobStatusMixin(models.AbstractModel):
    _name = "queue.job.status.mixin"
    _description = "Queue Job Status Mixin"

    running_job_names = fields.Char(compute="_compute_running_job_names")

    def _compute_running_job_names(self):
        """List the non-terminal queue jobs targeting each record."""
        self.running_job_names = False
        target_ids = self.ids
        if not target_ids:
            return

        queue_job = self.env["queue.job"].sudo()
        # Raw SQL does not trigger the ORM's automatic field flush.
        queue_job.flush_model(
            ["model_name", "state", "records", "name", "func_string", "method_name"]
        )
        self.env.cr.execute(
            SQL(
                """
                SELECT target.id,
                       string_agg(
                           DISTINCT COALESCE(
                               job.name, job.func_string, job.method_name
                           ),
                           ', '
                           ORDER BY COALESCE(
                               job.name, job.func_string, job.method_name
                           )
                       )
                  FROM unnest(%s::integer[]) AS target(id)
                  JOIN %s AS job
                    ON %s @> jsonb_build_array(target.id)
                 WHERE job.model_name = %s
                   AND job.state = ANY(%s)
                 GROUP BY target.id
                """,
                target_ids,
                SQL.identifier(queue_job._table),
                JOB_RECORD_IDS_SQL,
                self._name,
                list(RUNNING_STATES),
            )
        )
        names_by_record_id = dict(self.env.cr.fetchall())
        for record in self:
            record.running_job_names = names_by_record_id.get(record.id, False)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == "form":
            for sheet in arch.xpath("/form/sheet"):
                label = self.env["ir.qweb"]._render(
                    "queue_job_is_running.running_job_banner", {}
                )
                sheet.addprevious(etree.fromstring(label))
        return arch, view
