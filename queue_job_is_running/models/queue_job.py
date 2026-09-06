# Copyright 2026 Ecosoft Co., Ltd. (https://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models
from odoo.tools import SQL, index_exists

from .constants import JOB_RECORD_IDS_SQL, RUNNING_RECORD_IDS_INDEX


class QueueJob(models.Model):
    _inherit = "queue.job"

    def init(self):
        result = super().init()
        if not index_exists(self._cr, RUNNING_RECORD_IDS_INDEX):
            self._cr.execute(
                SQL(
                    """
                CREATE INDEX %s
                ON %s
                USING gin ((%s) jsonb_path_ops)
                WHERE state IN (
                    'wait_dependencies', 'pending', 'enqueued', 'started'
                )
                    """,
                    SQL.identifier(RUNNING_RECORD_IDS_INDEX),
                    SQL.identifier(self._table),
                    JOB_RECORD_IDS_SQL,
                )
            )
        return result
