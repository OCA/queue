# -*- coding: utf-8 -*-
# Copyright 2017-2018 Tecnativa - Pedro M. Baeza
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import api, SUPERUSER_ID
from odoo.addons.queue_job.job import DONE


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
        if method:
            QueueJob.search(group['__domain']).write({
                'channel_method_name': '<%s>.%s' % (
                    method.im_class._name, method.__name__,
                ),
            })
    # recompute func_string after other addons have adapted their
    # args/kwargs/record_ids
    records = QueueJob.search([('state', 'not in', [DONE])])
    records._recompute_todo(QueueJob._fields['func_string'])
    records.recompute()
