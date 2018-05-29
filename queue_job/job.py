# Copyright 2013-2016 Camptocamp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import inspect
import functools
import logging
import uuid
import sys
from datetime import datetime, timedelta

import odoo

from .exception import (NoSuchJobError,
                        FailedJobError,
                        RetryableJobError)

CREATED = 'created'  # not a real state, used only for the on_* events
PENDING = 'pending'
ENQUEUED = 'enqueued'
DONE = 'done'
STARTED = 'started'
FAILED = 'failed'

STATES = [(PENDING, 'Pending'),
          (ENQUEUED, 'Enqueued'),
          (STARTED, 'Started'),
          (DONE, 'Done'),
          (FAILED, 'Failed')]

DEFAULT_PRIORITY = 10  # used by the PriorityQueue to sort the jobs
DEFAULT_MAX_RETRIES = 5
RETRY_INTERVAL = 10 * 60  # seconds

_logger = logging.getLogger(__name__)


class DelayableRecordset(object):
    """ Allow to delay a method for a recordset

    Usage::

        delayable = DelayableRecordset(recordset, priority=20)
        delayable.method(args, kwargs)

    ``method`` must be a method of the recordset's Model, decorated with
    :func:`~odoo.addons.queue_job.job.job`.

    The method call will be processed asynchronously in the job queue, with
    the passed arguments.


    """

    def __init__(self, recordset, priority=None, eta=None,
                 max_retries=None, description=None, channel=None):
        self.recordset = recordset
        self.priority = priority
        self.eta = eta
        self.max_retries = max_retries
        self.description = description
        self.channel = channel

    def __getattr__(self, name):
        if name in self.recordset:
            raise AttributeError(
                'only methods can be delayed (%s called on %s)' %
                (name, self.recordset)
            )
        recordset_method = getattr(self.recordset, name)
        if not getattr(recordset_method, 'delayable', None):
            raise AttributeError(
                'method %s on %s is not allowed to be delayed, '
                'it should be decorated with odoo.addons.queue_job.job.job' %
                (name, self.recordset)
            )

        def delay(*args, **kwargs):
            return Job.enqueue(recordset_method,
                               args=args,
                               kwargs=kwargs,
                               priority=self.priority,
                               max_retries=self.max_retries,
                               eta=self.eta,
                               description=self.description,
                               channel=self.channel)
        return delay

    def __str__(self):
        return "DelayableRecordset(%s%s)" % (
            self.recordset._name,
            getattr(self.recordset, '_ids', "")
        )

    __repr__ = __str__


class Job(object):
    """ A Job is a task to execute.

    .. attribute:: uuid

        Id (UUID) of the job.

    .. attribute:: state

        State of the job, can pending, enqueued, started, done or failed.
        The start state is pending and the final state is done.

    .. attribute:: retry

        The current try, starts at 0 and each time the job is executed,
        it increases by 1.

    .. attribute:: max_retries

        The maximum number of retries allowed before the job is
        considered as failed.

    .. attribute:: args

        Arguments passed to the function when executed.

    .. attribute:: kwargs

        Keyword arguments passed to the function when executed.

    .. attribute:: description

        Human description of the job.

    .. attribute:: func

        The python function itself.

    .. attribute:: model_name

        Odoo model on which the job will run.

    .. attribute:: priority

        Priority of the job, 0 being the higher priority.

    .. attribute:: date_created

        Date and time when the job was created.

    .. attribute:: date_enqueued

        Date and time when the job was enqueued.

    .. attribute:: date_started

        Date and time when the job was started.

    .. attribute:: date_done

        Date and time when the job was done.

    .. attribute:: result

        A description of the result (for humans).

    .. attribute:: exc_info

        Exception information (traceback) when the job failed.

    .. attribute:: user_id

        Odoo user id which created the job

    .. attribute:: eta

        Estimated Time of Arrival of the job. It will not be executed
        before this date/time.

    .. attribute:: recordset

        Model recordset when we are on a delayed Model method

    .. attribute::channel

        The complete name of the channel to use to process the job. If
        provided it overrides the one defined on the job's function.

    """

    @classmethod
    def load(cls, env, job_uuid):
        """ Read a job from the Database"""
        stored = cls.db_record_from_uuid(env, job_uuid)
        if not stored:
            raise NoSuchJobError(
                'Job %s does no longer exist in the storage.' % job_uuid)

        args = stored.args
        kwargs = stored.kwargs
        method_name = stored.method_name

        model = env[stored.model_name]
        recordset = model.browse(stored.record_ids)
        method = getattr(recordset, method_name)

        dt_from_string = odoo.fields.Datetime.from_string
        eta = None
        if stored.eta:
            eta = dt_from_string(stored.eta)

        job_ = cls(method, args=args, kwargs=kwargs,
                   priority=stored.priority, eta=eta, job_uuid=stored.uuid,
                   description=stored.name, channel=stored.channel)

        if stored.date_created:
            job_.date_created = dt_from_string(stored.date_created)

        if stored.date_enqueued:
            job_.date_enqueued = dt_from_string(stored.date_enqueued)

        if stored.date_started:
            job_.date_started = dt_from_string(stored.date_started)

        if stored.date_done:
            job_.date_done = dt_from_string(stored.date_done)

        job_.state = stored.state
        job_.result = stored.result if stored.result else None
        job_.exc_info = stored.exc_info if stored.exc_info else None
        job_.user_id = stored.user_id.id if stored.user_id else None
        job_.model_name = stored.model_name if stored.model_name else None
        job_.retry = stored.retry
        job_.max_retries = stored.max_retries
        if stored.company_id:
            job_.company_id = stored.company_id.id
        return job_

    @classmethod
    def enqueue(cls, func, args=None, kwargs=None,
                priority=None, eta=None, max_retries=None, description=None,
                channel=None):
        """Create a Job and enqueue it in the queue. Return the job uuid.

        This expects the arguments specific to the job to be already extracted
        from the ones to pass to the job function.

        """
        new_job = cls(func=func, args=args,
                      kwargs=kwargs, priority=priority, eta=eta,
                      max_retries=max_retries, description=description,
                      channel=channel)
        new_job.store()
        _logger.debug(
            "enqueued %s:%s(*%r, **%r) with uuid: %s",
            new_job.recordset,
            new_job.method_name,
            new_job.args,
            new_job.kwargs,
            new_job.uuid
        )
        new_job.trigger_event_change(CREATED)
        return new_job

    @staticmethod
    def db_record_from_uuid(env, job_uuid):
        model = env['queue.job'].sudo()
        record = model.search([('uuid', '=', job_uuid)], limit=1)
        return record.with_env(env)

    def __init__(self, func,
                 args=None, kwargs=None, priority=None,
                 eta=None, job_uuid=None, max_retries=None,
                 description=None, channel=None):
        """ Create a Job

        :param func: function to execute
        :type func: function
        :param args: arguments for func
        :type args: tuple
        :param kwargs: keyworkd arguments for func
        :type kwargs: dict
        :param priority: priority of the job,
                         the smaller is the higher priority
        :type priority: int
        :param eta: the job can be executed only after this datetime
                           (or now + timedelta)
        :type eta: datetime or timedelta
        :param job_uuid: UUID of the job
        :param max_retries: maximum number of retries before giving up and set
            the job state to 'failed'. A value of 0 means infinite retries.
        :param description: human description of the job. If None, description
            is computed from the function doc or name
        :param channel: The complete channel name to use to process the job.
        :param env: Odoo Environment
        :type env: :class:`odoo.api.Environment`
        """
        if args is None:
            args = ()
        if isinstance(args, list):
            args = tuple(args)
        assert isinstance(args, tuple), "%s: args are not a tuple" % args
        if kwargs is None:
            kwargs = {}

        assert isinstance(kwargs, dict), "%s: kwargs are not a dict" % kwargs

        if not _is_model_method(func):
            raise TypeError("Job accepts only methods of Models")

        self._db_record = None
        self._func = None

        recordset = func.__self__
        env = recordset.env
        self.model_name = recordset._name
        self.method_name = func.__name__
        self.recordset = recordset

        self.env = env
        self.job_model = self.env['queue.job']
        self.job_model_name = 'queue.job'

        self.state = PENDING

        self.retry = 0
        if max_retries is None:
            self.max_retries = DEFAULT_MAX_RETRIES
        else:
            self.max_retries = max_retries

        self._uuid = job_uuid

        self.args = args
        self.kwargs = kwargs

        self.priority = priority
        if self.priority is None:
            self.priority = DEFAULT_PRIORITY

        self.date_created = datetime.now()
        self._description = description

        self.date_enqueued = None
        self.date_started = None
        self.date_done = None

        self.result = None
        self.exc_info = None

        self.user_id = env.uid
        if 'company_id' in env.context:
            company_id = env.context['company_id']
        else:
            company_model = env['res.company']
            company_model = company_model.sudo(self.user_id)
            company_id = company_model._company_default_get(
                object='queue.job',
                field='company_id'
            ).id
        self.company_id = company_id
        self._eta = None
        self.eta = eta
        self.channel = channel

    def perform(self):
        """ Execute the job.

        The job is executed with the user which has initiated it.
        """
        self.retry += 1
        try:
            self.result = self.func(*tuple(self.args), **self.kwargs)
        except RetryableJobError as err:
            if err.ignore_retry:
                self.retry -= 1
                raise
            elif not self.max_retries:  # infinite retries
                raise
            elif self.retry >= self.max_retries:
                type_, value, traceback = sys.exc_info()
                # change the exception type but keep the original
                # traceback and message:
                # http://blog.ianbicking.org/2007/09/12/re-raising-exceptions/
                new_exc = FailedJobError("Max. retries (%d) reached: %s" %
                                         (self.max_retries, value or type_)
                                         )
                raise new_exc from err
            raise
        return self.result

    def store(self):
        """ Store the Job """
        vals = {'state': self.state,
                'priority': self.priority,
                'retry': self.retry,
                'max_retries': self.max_retries,
                'exc_info': self.exc_info,
                'user_id': self.user_id or self.env.uid,
                'company_id': self.company_id,
                'result': str(self.result) if self.result else False,
                'date_enqueued': False,
                'date_started': False,
                'date_done': False,
                'eta': False,
                }

        dt_to_string = odoo.fields.Datetime.to_string
        if self.date_enqueued:
            vals['date_enqueued'] = dt_to_string(self.date_enqueued)
        if self.date_started:
            vals['date_started'] = dt_to_string(self.date_started)
        if self.date_done:
            vals['date_done'] = dt_to_string(self.date_done)
        if self.eta:
            vals['eta'] = dt_to_string(self.eta)

        db_record = self.db_record()
        if db_record:
            db_record.write(vals)
        else:
            date_created = dt_to_string(self.date_created)
            # The following values must never be modified after the
            # creation of the job
            vals.update({'uuid': self.uuid,
                         'name': self.description,
                         'date_created': date_created,
                         'model_name': self.model_name,
                         'method_name': self.method_name,
                         'record_ids': self.recordset.ids,
                         'args': self.args,
                         'kwargs': self.kwargs,
                         })
            # it the channel is not specified, lets the job_model compute
            # the right one to use
            if self.channel:
                vals.update({'channel': self.channel})

            sudo_job_model = self.env[self.job_model_name].sudo()
            self._db_record = sudo_job_model.create(vals)

    def trigger_event_change(self, event):
        events = {
            CREATED: self.func.on_create,
            STARTED: self.func.on_start,
            DONE: self.func.on_done,
            FAILED: self.func.on_failure,
        }
        action = events[event]
        if not action:
            return
        if isinstance(action, str):
            try:
                getattr(self.db_record(), action)()
            except AttributeError:
                _logger.error(
                    '%s could not be called when the job became "%s"'
                    ' because this method does not exist on queue.job',
                    action, event
                )
        else:
            if isinstance(action, NotifyWarnMessage):
                self.db_record().notify_warn(**action)
            else:
                self.db_record().notify(**action)

    def db_record(self):
        if not self._db_record:
            self._db_record = self.db_record_from_uuid(self.env, self.uuid)
        return self._db_record

    @property
    def func(self):
        if not self._func:
            recordset = self.recordset.with_context(job_uuid=self.uuid)
            recordset = recordset.sudo(self.user_id)
            self._func = getattr(recordset, self.method_name)
        return self._func

    @property
    def description(self):
        if self._description:
            return self._description
        elif self.func.__doc__:
            return self.func.__doc__.splitlines()[0].strip()
        else:
            return '%s.%s' % (self.model_name, self.func.__name__)

    @property
    def uuid(self):
        """Job ID, this is an UUID """
        if self._uuid is None:
            self._uuid = str(uuid.uuid4())
        return self._uuid

    @property
    def eta(self):
        return self._eta

    @eta.setter
    def eta(self, value):
        if not value:
            self._eta = None
        elif isinstance(value, timedelta):
            self._eta = datetime.now() + value
        elif isinstance(value, int):
            self._eta = datetime.now() + timedelta(seconds=value)
        else:
            self._eta = value

    def set_pending(self, result=None, reset_retry=True):
        self.state = PENDING
        self.date_enqueued = None
        self.date_started = None
        if reset_retry:
            self.retry = 0
        if result is not None:
            self.result = result

    def set_enqueued(self):
        self.state = ENQUEUED
        self.date_enqueued = datetime.now()
        self.date_started = None

    def set_started(self):
        self.state = STARTED
        self.date_started = datetime.now()
        self.trigger_event_change(STARTED)

    def set_done(self, result=None):
        self.state = DONE
        self.exc_info = None
        self.date_done = datetime.now()
        if result is not None:
            self.result = result
        self.trigger_event_change(DONE)

    def set_failed(self, exc_info=None):
        self.state = FAILED
        if exc_info is not None:
            self.exc_info = exc_info
        self.trigger_event_change(FAILED)

    def __repr__(self):
        return '<Job %s, priority:%d>' % (self.uuid, self.priority)

    def _get_retry_seconds(self, seconds=None):
        retry_pattern = self.func.retry_pattern
        if not seconds and retry_pattern:
            # ordered from higher to lower count of retries
            patt = sorted(retry_pattern.items(), key=lambda t: t[0])
            seconds = RETRY_INTERVAL
            for retry_count, postpone_seconds in patt:
                if self.retry >= retry_count:
                    seconds = postpone_seconds
                else:
                    break
        elif not seconds:
            seconds = RETRY_INTERVAL
        return seconds

    def postpone(self, result=None, seconds=None):
        """ Write an estimated time arrival to n seconds
        later than now. Used when an retryable exception
        want to retry a job later. """
        eta_seconds = self._get_retry_seconds(seconds)
        self.eta = timedelta(seconds=eta_seconds)
        self.exc_info = None
        if result is not None:
            self.result = result

    def related_action(self):
        if not hasattr(self.func, 'related_action'):
            return None
        if not self.func.related_action:
            return None
        if not isinstance(self.func.related_action, str):
            raise ValueError('related_action must be the name of the '
                             'method on queue.job as string')
        action = getattr(self.db_record(), self.func.related_action)
        return action(**self.func.kwargs)


def _is_model_method(func):
    return (inspect.ismethod(func) and
            isinstance(func.__self__.__class__, odoo.models.MetaModel))


def job(func=None, default_channel='root', retry_pattern=None,
        on_create=None, on_start=None, on_done=None, on_failure=None):
    """ Decorator for jobs.

    Optional argument:

    :param default_channel: the channel wherein the job will be assigned. This
                            channel is set at the installation of the module
                            and can be manually changed later using the views.
    :param retry_pattern: The retry pattern to use for postponing a job.
                          If a job is postponed and there is no eta
                          specified, the eta will be determined from the
                          dict in retry_pattern. When no retry pattern
                          is provided, jobs will be retried after
                          :const:`RETRY_INTERVAL` seconds.
    :type retry_pattern: dict(retry_count,retry_eta_seconds)
    :param on_create: name of the method on ``queue.job`` to call on creation
    :type on_create: str
    :param on_start: name of the method on ``queue.job`` to call on start
    :type on_start: str
    :param on_done: name of the method on ``queue.job`` to call on done
    :type on_done: str
    :param on_failure: name of the method on ``queue.job`` to call on failure
    :type on_failure: str

    Indicates that a method of a Model can be delayed in the Job Queue.

    When a method has the ``@job`` decorator, its calls can then be delayed
    with::

        recordset.with_delay(priority=10).the_method(args, **kwargs)

    Where ``the_method`` is the method decorated with ``@job``. Its arguments
    and keyword arguments will be kept in the Job Queue for its asynchronous
    execution.

    ``default_channel`` indicates in which channel the job must be executed

    ``retry_pattern`` is a dict where keys are the count of retries and the
    values are the delay to postpone a job.

    Example:

    .. code-block:: python

        class ProductProduct(models.Model):
            _inherit = 'product.product'

            @api.multi
            @job
            def export_one_thing(self, one_thing):
                # work
                # export one_thing

        # [...]

        env['a.model'].export_one_thing(the_thing_to_export)
        # => normal and synchronous function call

        env['a.model'].with_delay().export_one_thing(the_thing_to_export)
        # => the job will be executed as soon as possible

        delayable = env['a.model'].with_delay(priority=30, eta=60*60*5)
        delayable.export_one_thing(the_thing_to_export)
        # => the job will be executed with a low priority and not before a
        # delay of 5 hours from now

        @job(default_channel='root.subchannel')
        def export_one_thing(one_thing):
            # work
            # export one_thing

        @job(retry_pattern={1: 10 * 60,
                            5: 20 * 60,
                            10: 30 * 60,
                            15: 12 * 60 * 60})
        def retryable_example():
            # 5 first retries postponed 10 minutes later
            # retries 5 to 10 postponed 20 minutes later
            # retries 10 to 15 postponed 30 minutes later
            # all subsequent retries postponed 12 hours later
            raise RetryableJobError('Must be retried later')

        env['a.model'].with_delay().retryable_example()

    It can be user-friendly to pop a notification to the user when an
    action will be done in background and/or when it's done.

    The following events are triggered:

    * A new job is enqueued
    * Job started
    * Job finished
    * Job failed

    You can also send a simple notification with :func:`notify`` or
    :func:`notify_warn`:

    .. code-block:: python

            from odoo.addons.queue_job.job import job, notify

            @api.multi
            @job(on_done=notify(message='Partner exported'))
            def export_partner(self):
                # ...

    For more advanced messages, you can also create methods on the
    ``queue.job`` model and refer to them with a string. From these
    hook methods, you can call ``QueueJob.notify()`` or
    ``QueueJob.notify_warn()``.

    Example usage:

    .. code-block:: python

        class QueueJob(models.Model):
            _inherit = 'queue.job'

            @api.multi
            def on_export_partner_done(self):
                self.ensure_one()
                model = self.model_name
                partner = self.env[model].browse(self.record_ids)
                message = _('Partner %s exported') % partner.name
                self.notify(message=message)

        class ResPartner(models.Model):
            _inherit = 'res.partner'

            @api.multi
            @job(on_done='on_export_partner_done')
            def export_partner(self):
                # ...

    See also: :py:func:`related_action` a related action can be attached
    to a job

    """
    if func is None:
        return functools.partial(
            job, default_channel=default_channel,
            retry_pattern=retry_pattern,
            on_create=on_create, on_start=on_start, on_done=on_done,
            on_failure=on_failure
        )

    def delay_from_model(*args, **kwargs):
        raise AttributeError(
            "method.delay() can no longer be used, the general form is "
            "env['res.users'].with_delay().method()"
            )

    assert default_channel == 'root' or default_channel.startswith('root.'), (
        "The channel path must start by 'root'")
    assert retry_pattern is None or isinstance(retry_pattern, dict), (
        "retry_pattern must be a dict"
    )

    delay_func = delay_from_model

    func.delayable = True
    func.delay = delay_func
    func.retry_pattern = retry_pattern
    func.default_channel = default_channel
    func.on_create = on_create
    func.on_start = on_start
    func.on_done = on_done
    func.on_failure = on_failure
    return func


def related_action(action=None, **kwargs):
    """ Attach a *Related Action* to a job.

    A *Related Action* will appear as a button on the Odoo view.
    The button will execute the action, usually it will open the
    form view of the record related to the job.

    The ``action`` must be a method on the `queue.job` model.

    Example usage:

    .. code-block:: python

        class QueueJob(models.Model):
            _inherit = 'queue.job'

            @api.multi
            def related_action_partner(self):
                self.ensure_one()
                model = self.model_name
                partner = self.env[model].browse(self.record_ids)
                # possibly get the real ID if partner_id is a binding ID
                action = {
                    'name': _("Partner"),
                    'type': 'ir.actions.act_window',
                    'res_model': model,
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_id': partner.id,
                }
                return action

        class ResPartner(models.Model):
            _inherit = 'res.partner'

            @api.multi
            @job
            @related_action(action='related_action_partner')
            def export_partner(self):
                # ...

    The kwargs are transmitted to the action:

    .. code-block:: python

        class QueueJob(models.Model):
            _inherit = 'queue.job'

            @api.multi
            def related_action_product(self, extra_arg=1):
                assert extra_arg == 2
                model = self.model_name
                ...

        class ProductProduct(models.Model):
            _inherit = 'product.product'

            @api.multi
            @job
            @related_action(action='related_action_product', extra_arg=2)
            def export_product(self):
                # ...

    """
    def decorate(func):
        func.related_action = action
        func.kwargs = kwargs
        return func
    return decorate


class NotifyMessage(dict):
    """Used as a normal dict

    Used to differentiate normal notifications and warn notifications
    """


class NotifyWarnMessage(dict):
    """Used as a normal dict

    Used to differentiate normal notifications and warn notifications
    """


def _prepare_notify_content(message, title=None, sticky=None, **kwargs):
    message = {'message': message}
    if title is not None:
        message['title'] = title
    if sticky is not None:
        message['sticky'] = sticky
    if kwargs:
        message.update(**kwargs)
    return message


def notify(message, title=None, sticky=None, **kwargs):
    return NotifyMessage(**_prepare_notify_content(
        message, title=title, sticky=sticky, **kwargs
    ))


def notify_warn(message, title=None, sticky=None, **kwargs):
    return NotifyWarnMessage(**_prepare_notify_content(
        message, title=title, sticky=sticky, **kwargs
    ))
