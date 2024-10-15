from openupgradelib import openupgrade


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
                cr.execute(f"""
                    UPDATE {table}
                    SET {column} = {column}::jsonb
                    WHERE {column} IS NOT NULL
                """)
