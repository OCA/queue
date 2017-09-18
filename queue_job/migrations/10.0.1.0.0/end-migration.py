# -*- coding: utf-8 -*-
# Copyright 2017 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Now that everything has been loaded, compute the value of
    channel_method_name.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    jobs = env['queue.job'].search([])
    for job in jobs:
        if job.model_name not in env:
            continue
        model = env[job.model_name]
        method = getattr(model, job.method_name, False)
        if method:
            job.channel_method_name = '<%s>.%s' % (
                method.im_class._name, method.__name__,
            )
