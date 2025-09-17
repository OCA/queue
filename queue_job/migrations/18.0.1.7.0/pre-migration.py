# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # Remove cron garbage collector
    openupgrade.delete_records_safely_by_xml_id(
        env,
        ["queue_job.ir_cron_queue_job_garbage_collector"],
    )
