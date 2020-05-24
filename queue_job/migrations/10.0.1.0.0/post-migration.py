# -*- coding: utf-8 -*-
# Copyright 2018 Tecnativa - Pedro M. Baeza
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)


def migrate(cr, version):
    """Extract from old `func_name` field the name of the method to be put
    on `method_name`.
    """
    if not version:
        return
    cr.execute(
        """UPDATE queue_job
        SET method_name = reverse(split_part(reverse(func_name), '.', 1))"""
    )
