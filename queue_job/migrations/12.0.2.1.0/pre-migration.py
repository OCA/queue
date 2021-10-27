# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging

from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Disable trigger otherwise the update takes ages.
    cr.execute(
        """
        ALTER TABLE queue_job DISABLE TRIGGER queue_job_notify;
    """
    )
    if not column_exists(cr, "queue_job", "records"):
        cr.execute(
            """
            ALTER TABLE queue_job
            ADD COLUMN records text;
        """
        )
    cr.execute(
        """
    UPDATE queue_job
    SET records = '{"_type": "odoo_recordset"'
    || ', "model": "' || model_name || '"'
    || ', "uid": ' || user_id
    || ', "ids": ' || record_ids
    || '}'
    WHERE records IS NULL;
    """
    )
    cr.execute(
        """
        ALTER TABLE queue_job ENABLE TRIGGER queue_job_notify;
    """
    )
