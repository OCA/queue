# -*- coding: utf-8 -*-
# Copyright 2017 Tecnativa - Vicent Cubells
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).


def migrate(cr, version):
    if not version:
        return
    # In order to migrate connector from v9 to v10, we need to set
    # connector module state to 'to upgrade'. If this is not done, all
    # connector.* xmlids are removed due to the module renaming done by
    # OpenUpgrade. In the future the approach sketched in
    # https://github.com/OCA/queue/pull/23#issuecomment-325706811
    # may provide a more generic solution.
    cr.execute("""
        UPDATE ir_module_module
        SET state='to upgrade'
        WHERE name='connector'
    """)
    try:
        from openupgradelib import openupgrade
        openupgrade.rename_xmlids(
            cr, [
                ('queue_job.group_connector_manager',
                 'queue_job.group_queue_job_manager',)
            ],
        )
    except ImportError:
        pass
