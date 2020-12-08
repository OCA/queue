# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging

import odoo

logger = logging.getLogger(__name__)


def uninstall_hook(cr, registry):
    logger.info("Notify jobrunner to remove this db")
    with odoo.sql_db.db_connect("postgres").cursor() as cr_postgres:
        cr_postgres.execute(
            "notify queue_job_db_listener, %s", ("remove {}".format(cr.dbname),)
        )
