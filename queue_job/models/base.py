# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import inspect

from odoo import models, api
from ..job import DelayableRecordset


class Base(models.AbstractModel):
    """ The base model, which is implicitly inherited by all models. """
    _inherit = 'base'

    @api.model_cr
    def _register_hook(self):
        """ register marked jobs """
        super(Base, self)._register_hook()
        job_methods = set()
        for attr_name in dir(self):
            # _cache on models is a lazy_property which raises an
            # AssertionError when called on a empty model, just skip it.
            if attr_name == '_cache':
                continue
            try:
                attr = getattr(self, attr_name)
            except AttributeError:
                continue
            if inspect.ismethod(attr) and getattr(attr, 'delayable', None):
                job_methods.add(attr)
        for job_method in job_methods:
            self.env['queue.job.function']._register_job(job_method)

    @api.multi
    def with_delay(self, priority=None, eta=None,
                   max_retries=None, description=None,
                   channel=None):
        """ Return a ``DelayableRecordset``

        The returned instance allow to enqueue any method of the recordset's
        Model which is decorated by :func:`~odoo.addons.queue_job.job.job`.

        Usage::

            self.env['res.users'].with_delay().write({'name': 'test'})

        In the line above, in so far ``write`` is allowed to be delayed with
        ``@job``, the write will be executed in an asynchronous job.


        :param priority: Priority of the job, 0 being the higher priority.
                         Default is 10.
        :param eta: Estimated Time of Arrival of the job. It will not be
                    executed before this date/time.
        :param max_retries: maximum number of retries before giving up and set
                            the job state to 'failed'. A value of 0 means
                            infinite retries.  Default is 5.
        :param description: human description of the job. If None, description
                            is computed from the function doc or name
        :param channel: the complete name of the channel to use to process
                        the function. If specified it overrides the one
                        defined on the function
        :return: instance of a DelayableRecordset
        :rtype: :class:`odoo.addons.queue_job.job.DelayableRecordset`

        """
        return DelayableRecordset(self, priority=priority,
                                  eta=eta,
                                  max_retries=max_retries,
                                  description=description,
                                  channel=channel)
