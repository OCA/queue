# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)


def migrate(cr, version):
    # Deactivate cron garbage collector
    cr.execute(
        """
            UPDATE
                ir_cron
            SET
                active=False
            WHERE id IN (
                SELECT res_id
                FROM
                    ir_model_data
                WHERE
                    module='queue_job'
                    AND model='ir.cron'
                    AND name='ir_cron_queue_job_garbage_collector'
            );
        """
    )
