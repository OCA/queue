# Copyright 2019 Camptocamp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tools.sql import column_exists, rename_column


def migrate(cr, version):
    if column_exists(cr, "delay_export", "user_id"):
        rename_column(cr, "delay_export", "user_id", "__temp_user_id")
