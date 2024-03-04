# Copyright 2024 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class QueueJobFunction(models.Model):
    _inherit = "queue.job.function"

    is_web_notify_failure_enabled = fields.Boolean(
        string="Notify on failure",
        help="Display a notification in the user interface when the job fails.",
        default=False,
    )
