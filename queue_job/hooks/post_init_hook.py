# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging

import odoo

logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    # this is the trigger that sends notifications when jobs change
    logger.info("Create queue_job_notify trigger")
    cr.execute(
        """
            DROP TRIGGER IF EXISTS queue_job_notify ON queue_job;
            CREATE OR REPLACE
                FUNCTION queue_job_notify() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.state != 'done' THEN
                        PERFORM pg_notify('queue_job', OLD.uuid);
                    END IF;
                ELSE
                    PERFORM pg_notify('queue_job', NEW.uuid);
                END IF;
                RETURN NULL;
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER queue_job_notify
                AFTER INSERT OR UPDATE OR DELETE
                ON queue_job
                FOR EACH ROW EXECUTE PROCEDURE queue_job_notify();
        """
    )

    def notify():
        logger.info("Notify jobrunner to add this new db")
        with odoo.sql_db.db_connect("postgres").cursor() as cr_postgres:
            cr_postgres.execute(
                "notify queue_job_db_listener, %s", ("add {}".format(cr.dbname),)
            )

    # notify only when the module installation transaction has actually been committed
    # https://github.com/odoo/odoo/blob/aeebe275/odoo/modules/loading.py#L242
    cr.after("commit", notify)
