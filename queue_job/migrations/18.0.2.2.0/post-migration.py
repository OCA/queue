# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    if not version:
        return

    env["ir.config_parameter"].sudo().set_param(
        "queue_job.allow_commit_by_default", True
    )
    env["queue.job.function"].search([]).write({"allow_commit": True})
