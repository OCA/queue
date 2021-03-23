# Copyright 2013-2020 Camptocamp
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import hashlib
import inspect
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta
from socket import gethostname

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

    .. attribute::worker_pid

        The process ID of the worker that is executing or has executed a Job.

    ..attribute::worker_hostname

        The name of the host where the worker is running. (Useful in scaled
        environments to determine the node on which the process is executed.

    ..attribute::db_txid

        ID of the database transaction.

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
        job_.worker_hostname = stored.worker_hostname
        job_.db_txid = stored.db_txid
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
        """Create a Job

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
            self.env["queue.job.function"]
            .sudo()
            .job_config(
                self.env["queue.job.function"].job_function_name(
                    self.model_name, self.method_name
                )
            )
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
        self.worker_hostname = None
        self.db_txid = None

    def perform(self):
        """Execute the job.

        The job is executed with the user which has initiated it.
        """
        self.retry += 1
        try:
            # Get and store the transaction ID of the job
            self.set_db_txid()
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
        vals = {
            "state": self.state,
            "priority": self.priority,
            "retry": self.retry,
            "max_retries": self.max_retries,
            "exc_info": self.exc_info,
            "company_id": self.company_id,
            "result": str(self.result) if self.result else False,
            "date_enqueued": False,
            "date_started": False,
            "date_done": False,
            "eta": False,
            "identity_key": False,
            "worker_pid": self.worker_pid,
            "worker_hostname": self.worker_hostname,
        }

        if self.date_enqueued:
            vals["date_enqueued"] = self.date_enqueued
        if self.date_started:
            vals["date_started"] = self.date_started
        if self.date_done:
            vals["date_done"] = self.date_done
        if self.eta:
            vals["eta"] = self.eta
        if self.identity_key:
            vals["identity_key"] = self.identity_key
        if self.db_txid:
            vals["db_txid"] = self.db_txid

        job_model = self.env["queue.job"]
        # The sentinel is used to prevent edition sensitive fields (such as
        # method_name) from RPC methods.
        edit_sentinel = job_model.EDIT_SENTINEL

        db_record = self.db_record()
        if db_record:
            db_record.with_context(_job_edit_sentinel=edit_sentinel).write(vals)
        else:
            date_created = self.date_created
            # The following values must never be modified after the
            # creation of the job
            vals.update(
                {
                    "uuid": self.uuid,
                    "name": self.description,
                    "date_created": date_created,
                    "method_name": self.method_name,
                    "records": self.recordset,
                    "args": self.args,
                    "kwargs": self.kwargs,
                }
            )
            # it the channel is not specified, lets the job_model compute
            # the right one to use
            if self.channel:
                vals.update({"channel": self.channel})

            job_model.with_context(_job_edit_sentinel=edit_sentinel).sudo().create(vals)

    def db_record(self):
        return self.db_record_from_uuid(self.env, self.uuid)

    @property
    def func(self):
        recordset = self.recordset.with_context(job_uuid=self.uuid)
        return getattr(recordset, self.method_name)

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

    def get_db_txid(self):
        """
        Get the current if of the database transaction the job is running in. Only store
        the 32bit representation variant in the database so it can be compared directly
        to the 'backend_xid' in pg_stat_activity.
        """
        if self.env.cr._cnx.server_version >= 130000:
            self.env.cr.execute(
                "SELECT (pg_current_xact_id()::text::bigint % (2^32)::bigint)::text"
            )
        else:
            self.env.cr.execute("SELECT (txid_current() % (2^32)::bigint)::text;")
        return self.env.cr.fetchone()[0]

    def set_db_txid(self):
        """
        Use a new cursor to update the queue_job record of this job with the
        transaction ID the process is running in. The new cursor is necessary because
        after each commit the transaction ID changes (cfr. stored() is executed), which
        makes the transaction ID useless otherwise.
        """
        tx_id = self.get_db_txid()
        db_record = self.db_record()
        if not db_record:
            return
        with odoo.sql_db.db_connect(self.env.cr.dbname).cursor() as separate_cr:
            separate_cr.execute(
                "UPDATE queue_job SET db_txid = %(tx_id)s WHERE id = %(rec_id)s;",
                {"tx_id": tx_id, "rec_id": db_record.id},
            )
            separate_cr.commit()

    def set_pending(self, result=None, reset_retry=True):
        self.state = PENDING
        self.date_enqueued = None
        self.date_started = None
        self.worker_pid = None
        self.worker_hostname = None
        self.db_txid = None
        if reset_retry:
            self.retry = 0
        if result is not None:
            self.result = result

    def set_enqueued(self):
        self.state = ENQUEUED
        self.date_enqueued = datetime.now()
        self.date_started = None
        self.worker_pid = None
        self.worker_hostname = None
        self.db_txid = None

    def set_started(self):
        self.state = STARTED
        self.date_started = datetime.now()
        self.worker_pid = os.getpid()
        self.worker_hostname = gethostname()

    def set_done(self, result=None):
        self.state = DONE
        self.exc_info = None
        self.date_done = datetime.now()
        if result is not None:
            self.result = result

    def set_failed(self, exc_info=None):
        self.state = FAILED
        if exc_info is not None:
            self.exc_info = exc_info

    def __repr__(self):
        return "<Job %s, priority:%d>" % (self.uuid, self.priority)

    def _get_retry_seconds(self, seconds=None):
        retry_pattern = self.job_config.retry_pattern
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
        self.exc_info = None
        if result is not None:
            self.result = result

    def related_action(self):
        record = self.db_record()
        if not self.job_config.related_action_enable:
            return None

        funcname = self.job_config.related_action_func_name
        if not funcname:
            funcname = record._default_related_action
        if not isinstance(funcname, str):
            raise ValueError(
                "related_action must be the name of the "
                "method on queue.job as string"
            )
        action = getattr(record, funcname)
        action_kwargs = self.job_config.related_action_kwargs
        return action(**action_kwargs)


def _is_model_method(func):
    return inspect.ismethod(func) and isinstance(
        func.__self__.__class__, odoo.models.MetaModel
    )
