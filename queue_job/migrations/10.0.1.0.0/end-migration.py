# -*- coding: utf-8 -*-
# Copyright 2017-2018 Tecnativa - Pedro M. Baeza
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
import logging

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Now that everything has been loaded, compute the value of
    channel_method_name.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    logger = logging.getLogger("odoo.addons.queue.migrations")
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
    records = env["queue.job"].search([])
    total = len(records)
    count = 0
    error = 0
    for record in records:
        count += 1
        if not count % 1000:
            logger.info("Recomputing func_string of job %s of %s",
                        count, total)
        try:
            record._compute_func_string()
        except KeyError:  # unknown model or non-compliant arguments
            error += 1
            logger.debug("Could not recompute func_string of queue.job#%s",
                         record.id)

    if error:
        logger.warning("Could not recompute func_string of %s jobs", error)
