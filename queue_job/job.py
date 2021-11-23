# Copyright 2013-2020 Camptocamp
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import functools
import hashlib
import inspect
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta

import odoo

from .exception import FailedJobError, NoSuchJobError, RetryableJobError

PENDING = "pending"
ENQUEUED = "enqueued"
DONE = "done"
STARTED = "started"
FAILED = "failed"

STATES = [
    (PENDING, "Pending"),
    (ENQUEUED, "Enqueued"),
    (STARTED, "Started"),
    (DONE, "Done"),
    (FAILED, "Failed"),
]

DEFAULT_PRIORITY = 10  # used by the PriorityQueue to sort the jobs
DEFAULT_MAX_RETRIES = 5
RETRY_INTERVAL = 10 * 60  # seconds

_logger = logging.getLogger(__name__)


class DelayableRecordset(object):
    """Allow to delay a method for a recordset

    Usage::

        delayable = DelayableRecordset(recordset, priority=20)
        delayable.method(args, kwargs)

    The method call will be processed asynchronously in the job queue, with
    the passed arguments.

    This class will generally not be used directly, it is used internally
    by :meth:`~odoo.addons.queue_job.models.base.Base.with_delay`
    """

    def __init__(
        self,
        recordset,
        priority=None,
        eta=None,
        max_retries=None,
        description=None,
        channel=None,
        identity_key=None,
    ):
        self.recordset = recordset
        self.priority = priority
        self.eta = eta
        self.max_retries = max_retries
        self.description = description
        self.channel = channel
        self.identity_key = identity_key

    def __getattr__(self, name):
        if name in self.recordset:
            raise AttributeError(
                "only methods can be delayed ({} called on {})".format(
                    name, self.recordset
                )
            )
        recordset_method = getattr(self.recordset, name)

        def delay(*args, **kwargs):
            return Job.enqueue(
                recordset_method,
                args=args,
                kwargs=kwargs,
                priority=self.priority,
                max_retries=self.max_retries,
                eta=self.eta,
                description=self.description,
                channel=self.channel,
                identity_key=self.identity_key,
            )

        return delay

    def __str__(self):
        return "DelayableRecordset({}{})".format(
            self.recordset._name, getattr(self.recordset, "_ids", "")
        )

    __repr__ = __str__


def identity_exact(job_):
    """Identity function using the model, method and all arguments as key

    When used, this identity key will have the effect that when a job should be
    created and a pending job with the exact same recordset and arguments, the
    second will not be created.

    It should be used with the ``identity_key`` argument:

    .. python::

        from odoo.addons.queue_job.job import identity_exact

        # [...]
            delayable = self.with_delay(identity_key=identity_exact)
            delayable.export_record(force=True)

    Alternative identity keys can be built using the various fields of the job.
    For example, you could compute a hash using only some arguments of
    the job.

    .. python::

        def identity_example(job_):
            hasher = hashlib.sha1()
            hasher.update(job_.model_name)
            hasher.update(job_.method_name)
            hasher.update(str(sorted(job_.recordset.ids)))
            hasher.update(str(job_.args[1]))
            hasher.update(str(job_.kwargs.get('foo', '')))
            return hasher.hexdigest()

    Usually you will probably always want to include at least the name of the
    model and method.
    """
    hasher = hashlib.sha1()
    hasher.update(job_.model_name.encode("utf-8"))
    hasher.update(job_.method_name.encode("utf-8"))
    hasher.update(str(sorted(job_.recordset.ids)).encode("utf-8"))
    hasher.update(str(job_.args).encode("utf-8"))
    hasher.update(str(sorted(job_.kwargs.items())).encode("utf-8"))

    return hasher.hexdigest()


class Job(object):
    """A Job is a task to execute. It is the in-memory representation of a job.

    Jobs are stored in the ``queue.job`` Odoo Model, but they are handled
    through this class.

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

    .. attribute:: exc_name

        Exception error name when the job failed.

    .. attribute:: exc_message

        Exception error message when the job failed.

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

    .. attribute::identity_key

        A key referencing the job, multiple job with the same key will not
        be added to a channel if the existing job with the same key is not yet
        started or executed.

    """

    @classmethod
    def load(cls, env, job_uuid):
        """Read a job from the Database"""
        stored = cls.db_record_from_uuid(env, job_uuid)
        if not stored:
            raise NoSuchJobError(
                "Job %s does no longer exist in the storage." % job_uuid
            )
        return cls._load_from_db_record(stored)

    @classmethod
    def _load_from_db_record(cls, job_db_record):
        stored = job_db_record

        args = stored.args
        kwargs = stored.kwargs
        method_name = stored.method_name

        recordset = stored.records
        method = getattr(recordset, method_name)

        eta = None
        if stored.eta:
            eta = stored.eta

        job_ = cls(
            method,
            args=args,
            kwargs=kwargs,
            priority=stored.priority,
            eta=eta,
            job_uuid=stored.uuid,
            description=stored.name,
            channel=stored.channel,
            identity_key=stored.identity_key,
        )

        if stored.date_created:
            job_.date_created = stored.date_created

        if stored.date_enqueued:
            job_.date_enqueued = stored.date_enqueued

        if stored.date_started:
            job_.date_started = stored.date_started

        if stored.date_done:
            job_.date_done = stored.date_done

        job_.state = stored.state
        job_.result = stored.result if stored.result else None
        job_.exc_info = stored.exc_info if stored.exc_info else None
        job_.retry = stored.retry
        job_.max_retries = stored.max_retries
        if stored.company_id:
            job_.company_id = stored.company_id.id
        job_.identity_key = stored.identity_key
        job_.worker_pid = stored.worker_pid
        return job_

    def job_record_with_same_identity_key(self):
        """Check if a job to be executed with the same key exists."""
        existing = (
            self.env["queue.job"]
            .sudo()
            .search(
                [
                    ("identity_key", "=", self.identity_key),
                    ("state", "in", [PENDING, ENQUEUED]),
                ],
                limit=1,
            )
        )
        return existing

    @classmethod
    def enqueue(
        cls,
        func,
        args=None,
        kwargs=None,
        priority=None,
        eta=None,
        max_retries=None,
        description=None,
        channel=None,
        identity_key=None,
    ):
        """Create a Job and enqueue it in the queue. Return the job uuid.

        This expects the arguments specific to the job to be already extracted
        from the ones to pass to the job function.

        If the identity key is the same than the one in a pending job,
        no job is created and the existing job is returned

        """
        new_job = cls(
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            eta=eta,
            max_retries=max_retries,
            description=description,
            channel=channel,
            identity_key=identity_key,
        )
        if new_job.identity_key:
            existing = new_job.job_record_with_same_identity_key()
            if existing:
                _logger.debug(
                    "a job has not been enqueued due to having "
                    "the same identity key (%s) than job %s",
                    new_job.identity_key,
                    existing.uuid,
                )
                return Job._load_from_db_record(existing)
        new_job.store()
        _logger.debug(
            "enqueued %s:%s(*%r, **%r) with uuid: %s",
            new_job.recordset,
            new_job.method_name,
            new_job.args,
            new_job.kwargs,
            new_job.uuid,
        )
        return new_job

    @staticmethod
    def db_record_from_uuid(env, job_uuid):
        model = env["queue.job"].sudo()
        record = model.search([("uuid", "=", job_uuid)], limit=1)
        return record.with_env(env).sudo()

    def __init__(
        self,
        func,
        args=None,
        kwargs=None,
        priority=None,
        eta=None,
        job_uuid=None,
        max_retries=None,
        description=None,
        channel=None,
        identity_key=None,
    ):
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
        :param identity_key: A hash to uniquely identify a job, or a function
                             that returns this hash (the function takes the job
                             as argument)
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

        recordset = func.__self__
        env = recordset.env
        self.method_name = func.__name__
        self.recordset = recordset

        self.env = env
        self.job_model = self.env["queue.job"]
        self.job_model_name = "queue.job"

        self.job_config = (
            self.env["queue.job.function"].sudo().job_config(self.job_function_name)
        )

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

        if isinstance(identity_key, str):
            self._identity_key = identity_key
            self._identity_key_func = None
        else:
            # we'll compute the key on the fly when called
            # from the function
            self._identity_key = None
            self._identity_key_func = identity_key

        self.date_enqueued = None
        self.date_started = None
        self.date_done = None

        self.result = None
        self.exc_name = None
        self.exc_message = None
        self.exc_info = None

        if "company_id" in env.context:
            company_id = env.context["company_id"]
        else:
            company_id = env.company.id
        self.company_id = company_id
        self._eta = None
        self.eta = eta
        self.channel = channel
        self.worker_pid = None

    def perform(self):
        """Execute the job.

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
                new_exc = FailedJobError(
                    "Max. retries (%d) reached: %s" % (self.max_retries, value or type_)
                )
                raise new_exc from err
            raise
        return self.result

    def store(self):
        """Store the Job"""
        job_model = self.env["queue.job"]
        # The sentinel is used to prevent edition sensitive fields (such as
        # method_name) from RPC methods.
        edit_sentinel = job_model.EDIT_SENTINEL

        db_record = self.db_record()
        if db_record:
            db_record.with_context(_job_edit_sentinel=edit_sentinel).write(
                self._store_values()
            )
        else:
            job_model.with_context(_job_edit_sentinel=edit_sentinel).sudo().create(
                self._store_values(create=True)
            )

    def _store_values(self, create=False):
        vals = {
            "state": self.state,
            "priority": self.priority,
            "retry": self.retry,
            "max_retries": self.max_retries,
            "exc_name": self.exc_name,
            "exc_message": self.exc_message,
            "exc_info": self.exc_info,
            "company_id": self.company_id,
            "result": str(self.result) if self.result else False,
            "date_enqueued": False,
            "date_started": False,
            "date_done": False,
            "exec_time": False,
            "eta": False,
            "identity_key": False,
            "worker_pid": self.worker_pid,
        }

        if self.date_enqueued:
            vals["date_enqueued"] = self.date_enqueued
        if self.date_started:
            vals["date_started"] = self.date_started
        if self.date_done:
            vals["date_done"] = self.date_done
        if self.exec_time:
            vals["exec_time"] = self.exec_time
        if self.eta:
            vals["eta"] = self.eta
        if self.identity_key:
            vals["identity_key"] = self.identity_key

        if create:
            vals.update(
                {
                    "user_id": self.env.uid,
                    "channel": self.channel,
                    # The following values must never be modified after the
                    # creation of the job
                    "uuid": self.uuid,
                    "name": self.description,
                    "func_string": self.func_string,
                    "date_created": self.date_created,
                    "model_name": self.recordset._name,
                    "method_name": self.method_name,
                    "job_function_id": self.job_config.job_function_id,
                    "channel_method_name": self.job_function_name,
                    "records": self.recordset,
                    "args": self.args,
                    "kwargs": self.kwargs,
                }
            )

        vals_from_model = self._store_values_from_model()
        # Sanitize values: make sure you cannot screw core values
        vals_from_model = {k: v for k, v in vals_from_model.items() if k not in vals}
        vals.update(vals_from_model)
        return vals

    def _store_values_from_model(self):
        vals = {}
        value_handlers_candidates = (
            "_job_store_values_for_" + self.method_name,
            "_job_store_values",
        )
        for candidate in value_handlers_candidates:
            handler = getattr(self.recordset, candidate, None)
            if handler is not None:
                vals = handler(self)
        return vals

    @property
    def func_string(self):
        model = repr(self.recordset)
        args = [repr(arg) for arg in self.args]
        kwargs = ["{}={!r}".format(key, val) for key, val in self.kwargs.items()]
        all_args = ", ".join(args + kwargs)
        return "{}.{}({})".format(model, self.method_name, all_args)

    def db_record(self):
        return self.db_record_from_uuid(self.env, self.uuid)

    @property
    def func(self):
        recordset = self.recordset.with_context(job_uuid=self.uuid)
        return getattr(recordset, self.method_name)

    @property
    def job_function_name(self):
        func_model = self.env["queue.job.function"].sudo()
        return func_model.job_function_name(self.recordset._name, self.method_name)

    @property
    def identity_key(self):
        if self._identity_key is None:
            if self._identity_key_func:
                self._identity_key = self._identity_key_func(self)
        return self._identity_key

    @identity_key.setter
    def identity_key(self, value):
        if isinstance(value, str):
            self._identity_key = value
            self._identity_key_func = None
        else:
            # we'll compute the key on the fly when called
            # from the function
            self._identity_key = None
            self._identity_key_func = value

    @property
    def description(self):
        if self._description:
            return self._description
        elif self.func.__doc__:
            return self.func.__doc__.splitlines()[0].strip()
        else:
            return "{}.{}".format(self.model_name, self.func.__name__)

    @property
    def uuid(self):
        """Job ID, this is an UUID """
        if self._uuid is None:
            self._uuid = str(uuid.uuid4())
        return self._uuid

    @property
    def model_name(self):
        return self.recordset._name

    @property
    def user_id(self):
        return self.recordset.env.uid

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

    @property
    def channel(self):
        return self._channel or self.job_config.channel

    @channel.setter
    def channel(self, value):
        self._channel = value

    @property
    def exec_time(self):
        if self.date_done and self.date_started:
            return (self.date_done - self.date_started).total_seconds()
        return None

    def set_pending(self, result=None, reset_retry=True):
        self.state = PENDING
        self.date_enqueued = None
        self.date_started = None
        self.date_done = None
        self.worker_pid = None
        if reset_retry:
            self.retry = 0
        if result is not None:
            self.result = result

    def set_enqueued(self):
        self.state = ENQUEUED
        self.date_enqueued = datetime.now()
        self.date_started = None
        self.worker_pid = None

    def set_started(self):
        self.state = STARTED
        self.date_started = datetime.now()
        self.worker_pid = os.getpid()

    def set_done(self, result=None):
        self.state = DONE
        self.exc_name = None
        self.exc_info = None
        self.date_done = datetime.now()
        if result is not None:
            self.result = result

    def set_failed(self, **kw):
        self.state = FAILED
        for k, v in kw.items():
            if v is not None:
                setattr(self, k, v)

    def __repr__(self):
        return "<Job %s, priority:%d>" % (self.uuid, self.priority)

    def _get_retry_seconds(self, seconds=None):
        retry_pattern = self.job_config.retry_pattern
        if not retry_pattern:
            # TODO deprecated by :job-no-decorator:
            retry_pattern = getattr(self.func, "retry_pattern", None)
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
        """Postpone the job

        Write an estimated time arrival to n seconds
        later than now. Used when an retryable exception
        want to retry a job later.
        """
        eta_seconds = self._get_retry_seconds(seconds)
        self.eta = timedelta(seconds=eta_seconds)
        self.exc_name = None
        self.exc_info = None
        if result is not None:
            self.result = result

    def related_action(self):
        record = self.db_record()
        if not self.job_config.related_action_enable:
            return None

        funcname = self.job_config.related_action_func_name
        if not funcname and hasattr(self.func, "related_action"):
            # TODO deprecated by :job-no-decorator:
            funcname = self.func.related_action
            # decorator is set but empty: disable the default one
            if not funcname:
                return None

        if not funcname:
            funcname = record._default_related_action
        if not isinstance(funcname, str):
            raise ValueError(
                "related_action must be the name of the "
                "method on queue.job as string"
            )
        action = getattr(record, funcname)
        action_kwargs = self.job_config.related_action_kwargs
        if not action_kwargs:
            # TODO deprecated by :job-no-decorator:
            action_kwargs = getattr(self.func, "kwargs", {})
        return action(**action_kwargs)


def _is_model_method(func):
    return inspect.ismethod(func) and isinstance(
        func.__self__.__class__, odoo.models.MetaModel
    )


# TODO deprecated by :job-no-decorator:
def job(func=None, default_channel="root", retry_pattern=None):
    """Decorator for job methods.

    Deprecated. Use ``queue.job.function`` XML records (details in
    ``readme/USAGE.rst``).

    It enables the possibility to use a Model's method as a job function.

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


    See also: :py:func:`related_action` a related action can be attached
    to a job
    """
    if func is None:
        return functools.partial(
            job, default_channel=default_channel, retry_pattern=retry_pattern
        )

    xml_fields = [
        '    <field name="model_id" ref="[insert model xmlid]" />\n'
        '    <field name="method">_test_job</field>\n'
    ]
    if default_channel:
        xml_fields.append('    <field name="channel_id" ref="[insert channel xmlid]"/>')
    if retry_pattern:
        xml_fields.append('    <field name="retry_pattern">{retry_pattern}</field>')

    _logger.info(
        "@job is deprecated and no longer needed (on %s), it is advised to use an "
        "XML record (activate DEBUG log for snippet)",
        func.__name__,
    )
    if _logger.isEnabledFor(logging.DEBUG):
        xml_record = (
            '<record id="job_function_[insert model]_{method}"'
            ' model="queue.job.function">\n' + "\n".join(xml_fields) + "\n</record>"
        ).format(**{"method": func.__name__, "retry_pattern": retry_pattern})
        _logger.debug(
            "XML snippet (to complete) for replacing @job on %s:\n%s",
            func.__name__,
            xml_record,
        )

    def delay_from_model(*args, **kwargs):
        raise AttributeError(
            "method.delay() can no longer be used, the general form is "
            "env['res.users'].with_delay().method()"
        )

    assert default_channel == "root" or default_channel.startswith(
        "root."
    ), "The channel path must start by 'root'"
    assert retry_pattern is None or isinstance(
        retry_pattern, dict
    ), "retry_pattern must be a dict"

    delay_func = delay_from_model

    func.delayable = True
    func.delay = delay_func
    func.retry_pattern = retry_pattern
    func.default_channel = default_channel
    return func


# TODO deprecated by :job-no-decorator:
def related_action(action=None, **kwargs):
    """Attach a *Related Action* to a job (decorator)

    Deprecated. Use ``queue.job.function`` XML records (details in
    ``readme/USAGE.rst``).

    A *Related Action* will appear as a button on the Odoo view.
    The button will execute the action, usually it will open the
    form view of the record related to the job.

    The ``action`` must be a method on the `queue.job` model.

    Example usage:

    .. code-block:: python

        class QueueJob(models.Model):
            _inherit = 'queue.job'

            def related_action_partner(self):
                self.ensure_one()
                model = self.model_name
                partner = self.records
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

            @job
            @related_action(action='related_action_partner')
            def export_partner(self):
                # ...

    The kwargs are transmitted to the action:

    .. code-block:: python

        class QueueJob(models.Model):
            _inherit = 'queue.job'

            def related_action_product(self, extra_arg=1):
                assert extra_arg == 2
                model = self.model_name
                ...

        class ProductProduct(models.Model):
            _inherit = 'product.product'

            @job
            @related_action(action='related_action_product', extra_arg=2)
            def export_product(self):
                # ...

    """

    def decorate(func):
        related_action_dict = {
            "func_name": action,
        }
        if kwargs:
            related_action_dict["kwargs"] = kwargs

        xml_fields = (
            '    <field name="model_id" ref="[insert model xmlid]" />\n'
            '    <field name="method">_test_job</field>\n'
            '    <field name="related_action">{related_action}</field>'
        )

        _logger.info(
            "@related_action is deprecated and no longer needed (on %s),"
            " it is advised to use an XML record (activate DEBUG log for snippet)",
            func.__name__,
        )
        if _logger.isEnabledFor(logging.DEBUG):
            xml_record = (
                '<record id="job_function_[insert model]_{method}"'
                ' model="queue.job.function">\n' + xml_fields + "\n</record>"
            ).format(**{"method": func.__name__, "related_action": action})
            _logger.debug(
                "XML snippet (to complete) for replacing @related_action on %s:\n%s",
                func.__name__,
                xml_record,
            )

        func.related_action = action
        func.kwargs = kwargs
        return func

    return decorate
