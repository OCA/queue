# Copyright 2016 Cédric Pigeon
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResUsers(models.Model):

    _inherit = 'res.users'

    subscribe_job = fields.Boolean(
        'Job Notifications',
        default=True,
        help='If this flag is checked and the '
             'user is Connector Manager, he will '
             'receive job notifications.',
        index=True,
    )
