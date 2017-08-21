# -*- coding: utf-8 -*-
# Copyright 2017 Tecnativa - Vicent Cubells
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).


def migrate(cr, version):
    if not version:
        return
    # In order to migrate connector from v. 9.0 to v. 10.0, we need to set
    # connector module state to 'to upgrade'
    cr.execute("""
        UPDATE ir_module_module
        SET state='to upgrade'
        WHERE name='connector'
    """)
