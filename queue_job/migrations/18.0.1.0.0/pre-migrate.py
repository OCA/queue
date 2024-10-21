from openupgradelib import openupgrade

from odoo.tools import SQL


def migrate(cr, version):
    if not version:
        return

    # List of tables and their corresponding columns
    table_column_map = {
        "queue.job.function": ["retry_pattern", "related_action"],
        "queue.job": ["records", "args", "kwargs"],
    }

    for table, columns in table_column_map.items():
        for column in columns:
            if openupgrade.column_exists(cr, table, column):
                cr.execute(
                    SQL(
                        """
                    UPDATE %(table)s
                    SET %(column)s = %(column)s::jsonb
                    WHERE %(column)s IS NOT NULL
                """,
                        table=SQL.identifier(table),
                        column=SQL.identifier(column),
                    )
                )
