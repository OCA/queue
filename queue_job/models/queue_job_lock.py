# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class QueueJobLock(models.Model):
    _name = "queue.job.lock"
    _description = "Queue Job Lock"

    queue_job_id = fields.Many2one(
        comodel_name="queue.job",
        required=True,
        ondelete="cascade",
        index=True,
    )
