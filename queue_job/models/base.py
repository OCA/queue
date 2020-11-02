# Copyright 2016 Camptocamp
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import inspect
import logging
import os

from odoo import models

from ..job import DelayableRecordset

_logger = logging.getLogger(__name__)


class Base(models.AbstractModel):
    """The base model, which is implicitly inherited by all models.

    A new :meth:`~with_delay` method is added on all Odoo Models, allowing to
    postpone the execution of a job method in an asynchronous process.
    """

    _inherit = "base"

    # TODO deprecated by :job-no-decorator:
    def _register_hook(self):
        """Register marked jobs"""
        super(Base, self)._register_hook()
        job_methods = [
            method
            for __, method in inspect.getmembers(
                self.__class__, predicate=inspect.isfunction
            )
            if getattr(method, "delayable", None)
        ]
        for job_method in job_methods:
            self.env["queue.job.function"]._register_job(self, job_method)

    def with_delay(
        self,
        priority=None,
        eta=None,
        max_retries=None,
        description=None,
        channel=None,
        identity_key=None,
    ):
        """ Return a ``DelayableRecordset``

        The returned instance allows to enqueue any method of the recordset's
        Model.

        Usage::

            self.env['res.users'].with_delay().write({'name': 'test'})

        ``with_delay()`` accepts job properties which specify how the job will
        be executed.

        Usage with job properties::

            delayable = env['a.model'].with_delay(priority=30, eta=60*60*5)
            delayable.export_one_thing(the_thing_to_export)
            # => the job will be executed with a low priority and not before a
            # delay of 5 hours from now

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
        :param identity_key: key uniquely identifying the job, if specified
                             and a job with the same key has not yet been run,
                             the new job will not be added. It is either a
                             string, either a function that takes the job as
                             argument (see :py:func:`..job.identity_exact`).
        :return: instance of a DelayableRecordset
        :rtype: :class:`odoo.addons.queue_job.job.DelayableRecordset`

        Note for developers: if you want to run tests or simply disable
        jobs queueing for debugging purposes, you can:

            a. set the env var `TEST_QUEUE_JOB_NO_DELAY=1`
            b. pass a ctx key `test_queue_job_no_delay=1`

        In tests you'll have to mute the logger like:

            @mute_logger('odoo.addons.queue_job.models.base')
        """
        if os.getenv("TEST_QUEUE_JOB_NO_DELAY"):
            _logger.warn("`TEST_QUEUE_JOB_NO_DELAY` env var found. NO JOB scheduled.")
            return self
        if self.env.context.get("test_queue_job_no_delay"):
            _logger.warn("`test_queue_job_no_delay` ctx key found. NO JOB scheduled.")
            return self
        return DelayableRecordset(
            self,
            priority=priority,
            eta=eta,
            max_retries=max_retries,
            description=description,
            channel=channel,
            identity_key=identity_key,
        )
