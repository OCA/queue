# Copyright 2019 Camptocamp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, SUPERUSER_ID
from odoo.tools.sql import column_exists


def migrate(cr, version):
    if not column_exists(cr, "delay_export", "__temp_user_id"):
        return
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        field = env["delay.export"]._fields["user_ids"]
        rel, id1, id2 = field.relation, field.column1, field.column2
        env.cr.execute(
            """
            INSERT INTO %s (%s, %s)
            SELECT id, __temp_user_id
            FROM delay_export
            """
            % (rel, id1, id2)
        )
        env.cr.execute("ALTER TABLE delay_export DROP COLUMN __temp_user_id;")
