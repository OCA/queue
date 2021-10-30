# Copyright 2019 Versada UAB
# Copyright 2021 ACSONE SA/NV
# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).

import odoo


def migrate(cr, version):
    """Set "AutoVacuum Job Queue" cron job `state` to `code."""
    if not version:
        return
    with odoo.api.Environment.manage():
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        cron_job = env.ref(
            'queue_job.ir_cron_autovacuum_queue_jobs',
            raise_if_not_found=False)
        if cron_job and cron_job.exists() and cron_job.state != 'code':
            cron_job.state = 'code'
