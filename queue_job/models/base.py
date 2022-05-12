# Copyright 2016 Camptocamp
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import functools
import inspect
import logging
import os

from odoo import api, models

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

    def _patch_job_auto_delay(self, method_name, context_key=None):
        """Patch a method to be automatically delayed as job method when called

        This patch method has to be called in ``_register_hook`` (example
        below).

        When a method is patched, any call to the method will not directly
        execute the method's body, but will instead enqueue a job.

        When a ``context_key`` is set when calling ``_patch_job_auto_delay``,
        the patched method is automatically delayed only when this key is
        ``True`` in the caller's context. It is advised to patch the method
        with a ``context_key``, because making the automatic delay *in any
        case* can produce nasty and unexpected side effects (e.g. another
        module calls the method and expects it to be computed before doing
        something else, expecting a result, ...).

        A typical use case is when a method in a module we don't control is
        called synchronously in the middle of another method, and we'd like all
        the calls to this method become asynchronous.

        The options of the job usually passed to ``with_delay()`` (priority,
        description, identity_key, ...) can be returned in a dictionary by a
        method named after the name of the method suffixed by ``_job_options``
        which takes the same parameters as the initial method.

        It is still possible to force synchronous execution of the method by
        setting a key ``_job_force_sync`` to True in the environment context.

        Example patching the "foo" method to be automatically delayed as job
        (the job options method is optional):

        .. code-block:: python

            # original method:
            def foo(self, arg1):
                print("hello", arg1)

            def large_method(self):
                # doing a lot of things
                self.foo("world)
                # doing a lot of other things

            def button_x(self):
                self.with_context(auto_delay_foo=True).large_method()

            # auto delay patch:
            def foo_job_options(self, arg1):
                return {
                  "priority": 100,
                  "description": "Saying hello to {}".format(arg1)
                }

            def _register_hook(self):
                self._patch_method(
                    "foo",
                    self._patch_job_auto_delay("foo", context_key="auto_delay_foo")
                )
                return super()._register_hook()

        The result when ``button_x`` is called, is that a new job for ``foo``
        is delayed.
        """

        def auto_delay_wrapper(self, *args, **kwargs):
            # when no context_key is set, we delay in any case (warning, can be
            # dangerous)
            context_delay = self.env.context.get(context_key) if context_key else True
            if (
                self.env.context.get("job_uuid")
                or not context_delay
                or self.env.context.get("_job_force_sync")
                or self.env.context.get("test_queue_job_no_delay")
            ):
                # we are in the job execution
                return auto_delay_wrapper.origin(self, *args, **kwargs)
            else:
                # replace the synchronous call by a job on itself
                method_name = auto_delay_wrapper.origin.__name__
                job_options_method = getattr(
                    self, "{}_job_options".format(method_name), None
                )
                job_options = {}
                if job_options_method:
                    job_options.update(job_options_method(*args, **kwargs))
                delayed = self.with_delay(**job_options)
                return getattr(delayed, method_name)(*args, **kwargs)

        origin = getattr(self, method_name)
        return functools.update_wrapper(auto_delay_wrapper, origin)

    @api.model
    def _job_store_values(self, job):
        """Hook for manipulating job stored values.

        You can define a more specific hook for a job function
        by defining a method name with this pattern:

            `_queue_job_store_values_${func_name}`

        NOTE: values will be stored only if they match stored fields on `queue.job`.

        :param job: current queue_job.job.Job instance.
        :return: dictionary for setting job values.
        """
        return {}

    @api.model
    def _job_prepare_context_before_enqueue_keys(self):
        """Keys to keep in context of stored jobs

        Empty by default for backward compatibility.
        """
        # TODO: when migrating to 16.0, active the base context keys:
        # return ("tz", "lang", "allowed_company_ids", "force_company", "active_test")
        return ()

    def _job_prepare_context_before_enqueue(self):
        """Return the context to store in the jobs

        Can be used to keep only safe keys.
        """
        return {
            key: value
            for key, value in self.env.context.items()
            if key in self._job_prepare_context_before_enqueue_keys()
        }
