# -*- coding: utf-8 -*-
# Copyright 2018 Tecnativa - Pedro M. Baeza
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
import json
import logging
from cPickle import Unpickler
from StringIO import StringIO
from odoo.addons.queue_job.job import DONE
from odoo.addons.queue_job.fields import JobEncoder


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Extract from old `func_name` field the name of the method to be put
    on `method_name`. Drop notify trigger for drastically better performance.
    """
    if not version:
        return
    cr.execute(
        """
        DROP TRIGGER IF EXISTS queue_job_notify ON queue_job;
        UPDATE queue_job
        SET method_name = reverse(split_part(reverse(func_name), '.', 1))"""
    )
    migrate_args_kwargs(cr)


def migrate_args_kwargs(cr):
    """Extract args and kwargs from v9 func column, which is the tuple
    (func_name, args, kwargs) pickled in a binary string. Ignore done
    jobs for performance reasons"""
    cr.execute(
        'select id, func from queue_job where state not in %s',
        (tuple([DONE]),),
    )
    for _id, func in cr.fetchall():
        try:
            func_name, args, kwargs = Unpickler(StringIO(func)).load()
        except Exception:
            _logger.exception(
                'Failed to parse func column for queue_job#%s', _id,
            )
            continue
        cr.execute(
            'update queue_job set args=%s, kwargs=%s where id=%s',
            (
                json.dumps(args, cls=JobEncoder),
                json.dumps(kwargs, cls=JobEncoder),
                _id,
            ),
        )
