# -*- coding: utf-8 -*-
# Copyright 2017-2018 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Now that everything has been loaded, compute the value of
    channel_method_name.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    QueueJob = env['queue.job']
    groups = QueueJob.read_group(
        [], ['model_name', 'method_name'], ['model_name', 'method_name'],
        lazy=False,
    )
    for group in groups:
        if group['model_name'] not in env:
            continue
        model = env[group['model_name']]
        method = getattr(model, group['method_name'], False)
        QueueJob.search(group['__domain']).write({
            'channel_method_name': '<%s>.%s' % (
                method.im_class._name, method.__name__,
            ),
        })
