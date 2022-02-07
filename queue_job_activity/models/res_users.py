# Copyright 2022 ForgeFlow S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ResUsers(models.Model):

    _inherit = "res.users"

    job_activity = fields.Boolean(
        "Create Job Activities",
        default=True,
        help="If this flag is checked and the "
        "user is Connector Manager, he will "
        "assigned to activiies to review failed jobs.",
        index=True,
    )
