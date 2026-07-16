# Copyright 2013-2020 Camptocamp
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import hashlib
import inspect
import logging
import os
import sys
import uuid
import warnings
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any, NamedTuple

import odoo

from .exception import FailedJobError, NoSuchJobError, RetryableJobError

WAIT_DEPENDENCIES = "wait_dependencies"
PENDING = "pending"
ENQUEUED = "enqueued"
CANCELLED = "cancelled"
DONE = "done"
STARTED = "started"
FAILED = "failed"

STATES = [
    (WAIT_DEPENDENCIES, "Wait Dependencies"),
    (PENDING, "Pending"),
    (ENQUEUED, "Enqueued"),
    (STARTED, "Started"),
    (DONE, "Done"),
    (CANCELLED, "Cancelled"),
    (FAILED, "Failed"),
]

DEFAULT_PRIORITY = 10  # used by the PriorityQueue to sort the jobs
DEFAULT_MAX_RETRIES = 5
RETRY_INTERVAL = 10 * 60  # seconds

_logger = logging.getLogger(__name__)


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
    hasher = identity_exact_hasher(job_)
    return hasher.hexdigest()


def identity_exact_hasher(job_):
    """Prepare hasher object for identity_exact."""
    hasher = hashlib.sha1()
    hasher.update(job_.model_name.encode("utf-8"))
    hasher.update(job_.method_name.encode("utf-8"))
    hasher.update(str(sorted(job_.recordset.ids)).encode("utf-8"))
    hasher.update(str(job_.args).encode("utf-8"))
    hasher.update(str(sorted(job_.kwargs.items())).encode("utf-8"))
    return hasher


class JobSpec(NamedTuple):
    """Method call being enqueued to a Job (read-only)"""

    model_name: str
    method_name: str
    recordset: odoo.models.BaseModel
    args: tuple
    kwargs: dict
    uuid: str | None = None
    state: str = PENDING  # initial state can be pending or wait_dependencies

    @classmethod
    def from_call(cls, func, args=None, kwargs=None) -> "JobSpec":
        """Build the :class:`JobSpec` of a method call"""
        if not _is_model_method(func):
            raise TypeError("Job accepts only methods of Models")
        if args is None:
            args = ()
        if isinstance(args, list):
            args = tuple(args)
        assert isinstance(args, tuple), f"{args}: args are not a tuple"
        if kwargs is None:
            kwargs = {}
        assert isinstance(kwargs, dict), f"{kwargs}: kwargs are not a dict"
        recordset = func.__self__
        return JobSpec(recordset._name, func.__name__, recordset, args, kwargs)

    def compute_identity_key(
        self,
        identity_key: "str | Callable | None" = None,
    ) -> str | None:
        """Compute the identity key of a method call being enqueued.

        A callable identity key is invoked with the :class:`JobSpec`
        of the call.
        """
        if identity_key is None or isinstance(identity_key, str):
            return identity_key
        return identity_key(self)


# see what to do of this
def _run_job_function(func, args, kwargs, current_try, max_retries=None) -> Any:
    """Run a job function with the retry limits logic."""
    current_try += 1
    try:
        result = func(*tuple(args), **kwargs)
    except RetryableJobError as err:
        if err.ignore_retry:
            current_try -= 1
            raise
        elif not max_retries:  # infinite retries
            raise
        elif current_try >= max_retries:
            type_, value, _traceback = sys.exc_info()
            # change the exception type but keep the original
            # traceback and message:
            # http://blog.ianbicking.org/2007/09/12/re-raising-exceptions/
            new_exc = FailedJobError(
                "Max. retries (%d) reached: %s" % (max_retries, value or type_)
            )
            raise new_exc from err
        raise

    return result, current_try


def _normalize_eta(value) -> datetime | None:
    """Normalize an eta given as datetime, timedelta or seconds."""
    if not value:
        return None
    if isinstance(value, timedelta):
        return datetime.now() + value
    if isinstance(value, int):
        return datetime.now() + timedelta(seconds=value)
    return value


class JobPayload:
    """What a job executes: the recordset and the arguments.

    Built:

      * eagerly at enqueue time with the enqueue environment
      * on demand at loading/execution time with the execution environment

    """

    def __init__(self, recordset: odoo.models.BaseModel, args=None, kwargs=None):
        if args is None:
            args = ()
        if isinstance(args, list):
            args = tuple(args)
        assert isinstance(args, tuple), f"{args}: args are not a tuple"
        if kwargs is None:
            kwargs = {}
        assert isinstance(kwargs, dict), f"{kwargs}: kwargs are not a dict"
        self.recordset = recordset
        self.args = args
        self.kwargs = kwargs

    @classmethod
    def from_record(cls, db_record: odoo.models.BaseModel) -> "JobPayload":
        """Deserialize the payload columns of a job record."""
        return cls(
            db_record.records,
            tuple(db_record.args or ()),
            dict(db_record.kwargs or {}),
        )


class Job:
    """A Job is a task to execute. It is the in-memory representation of a job.

    Jobs are stored in the ``queue.job`` Odoo Model, but they are handled
    through this class.

    .. attribute:: uuid

        Id (UUID) of the job.

    .. attribute:: graph_uuid

        Shared UUID of the job's graph. Empty if the job is a single job.

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

    def __new__(cls, db_record=None, *args, **kwargs):
        # Catch calls to Job(func, ...) used before API changes
        if db_record is not None and not isinstance(db_record, odoo.models.BaseModel):
            # TODO: backward compatibility with a "shim"?
            # here db_record is a func, not a db_record
            return JobCompat(db_record, *args, **kwargs)
        return super().__new__(cls)

    @classmethod
    def load(cls, env: odoo.api.Environment, job_uuid: str) -> "Job":
        """Read a single job from the Database

        Raise an error if the job is not found.
        """
        stored = cls.db_records_from_uuids(env, [job_uuid])
        if not stored:
            raise NoSuchJobError(
                f"Job {job_uuid} does no longer exist in the database."
            )
        return cls(db_record=stored)

    @classmethod
    def load_many(
        cls, env: odoo.api.Environment, job_uuids: Sequence[str]
    ) -> set["Job"]:
        """Read jobs in batch from the Database

        Jobs not found are ignored.
        """
        recordset = cls.db_records_from_uuids(env, job_uuids)
        return {cls(db_record=record) for record in recordset}

    @staticmethod
    def db_records_from_uuids(
        env: odoo.api.Environment, job_uuids: Sequence[str]
    ) -> odoo.models.BaseModel:
        model = env["queue.job"].sudo()
        record = model.search([("uuid", "in", tuple(job_uuids))])
        return record.with_env(env).sudo()

    def db_record(self, env: odoo.api.Environment) -> odoo.models.BaseModel:
        """The ``queue.job`` record of the job, using env."""
        return self.db_records_from_uuids(env, [self.uuid])

    def __init__(self, db_record: odoo.models.BaseModel = None):
        """Build the job from its ``queue.job`` record"""
        if db_record is None:
            raise TypeError("TODO: explain how jobs are created")

        stored = db_record
        self._stored_id = stored.id
        self.method_name = stored.method_name
        self.model_name = stored.model_name
        self.user_id = stored.user_id.id if stored.user_id else None

        func_model = stored.env["queue.job.function"].sudo()
        self.job_function_name = func_model.job_function_name(
            stored.model_name, stored.method_name
        )
        self.job_config = func_model.job_config(self.job_function_name)

        self.state = stored.state
        self.retry = stored.retry
        self.max_retries = stored.max_retries
        self.uuid = stored.uuid
        self.graph_uuid = stored.graph_uuid if stored.graph_uuid else None
        self.priority = stored.priority
        self.date_created = stored.date_created or None
        self.date_enqueued = stored.date_enqueued or None
        self.date_started = stored.date_started or None
        self.date_done = stored.date_done or None
        self.date_cancelled = stored.date_cancelled or None
        self.description = stored.name
        self.identity_key = stored.identity_key or None
        self.result = stored.result if stored.result else None
        self.exc_name = stored.exc_name if stored.exc_name else None
        self.exc_message = stored.exc_message if stored.exc_message else None
        self.exc_info = stored.exc_info if stored.exc_info else None
        self.company_id = stored.company_id.id if stored.company_id else None
        self._eta = None
        if stored.eta:
            self.eta = stored.eta
        self._channel = stored.channel
        self.worker_pid = stored.worker_pid

        self._depends_on_uuids = set(stored.dependencies.get("depends_on", []))
        self._reverse_depends_on_uuids = set(
            stored.dependencies.get("reverse_depends_on", [])
        )

    def perform(self, env: odoo.api.Environment) -> Any:
        """Execute the job on ``env``

        The job is executed with the user which has initiated it.

        The payload (recordset, args, kwargs) is retrieved from  ``env``,
        and the job function runs on it, with the user which has initiated the
        job.

        The transaction of ``env`` is the responsibility of the caller: ``JobExecutor``
        passes its execution transaction.
        """
        payload = self.payload(env)
        recordset = payload.recordset.with_context(job_uuid=self.uuid)
        func = getattr(recordset, self.method_name)
        self.result, self.retry = _run_job_function(
            func, payload.args, payload.kwargs, self.retry, self.max_retries
        )

    def should_check_dependents(self):
        return any(self._reverse_depends_on_uuids)

    def payload(self, env: odoo.api.Environment) -> JobPayload:
        """The payload of the job in the ``env`` environment"""
        record = env["queue.job"].sudo().browse(self._stored_id)
        return JobPayload.from_record(record)

    def __eq__(self, other):
        return self.uuid == other.uuid

    def __hash__(self):
        return self.uuid.__hash__()

    @property
    def depends_on_uuids(self) -> set[str]:
        """UUIDs of the jobs this job depends on (no database access)."""
        return set(self._depends_on_uuids)

    @property
    def reverse_depends_on_uuids(self) -> set[str]:
        """UUIDs of the jobs depending on this job (no database access)."""
        return set(self._reverse_depends_on_uuids)

    def depends_on(self, env: odoo.api.Environment) -> "set[Job]":
        """The jobs this job depends on, loaded in ``env``, never kept."""
        return Job.load_many(env, self._depends_on_uuids)

    def reverse_depends_on(self, env: odoo.api.Environment) -> "set[Job]":
        """The jobs depending on this job (see :meth:`depends_on`)."""
        return Job.load_many(env, self._reverse_depends_on_uuids)

    @property
    def eta(self):
        return self._eta

    @eta.setter
    def eta(self, value):
        self._eta = _normalize_eta(value)

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

    def set_pending(
        self,
        result: Any = None,
        reset_retry: bool = True,
    ) -> None:
        self.state = PENDING
        self.date_enqueued = None
        self.date_started = None
        self.date_done = None
        self.worker_pid = None
        self.date_cancelled = None
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

    def set_cancelled(self, result=None):
        self.state = CANCELLED
        self.date_cancelled = datetime.now()
        if result is not None:
            self.result = result

    def set_failed(
        self,
        exc_name: str | None = None,
        exc_message: str | None = None,
        exc_info: str | None = None,
        **kwargs,
    ) -> None:
        self.state = FAILED

        if exc_name is not None:
            self.exc_name = exc_name
        if exc_message is not None:
            self.exc_message = exc_message
        if exc_info is not None:
            self.exc_info = exc_info
        if kwargs:
            # TODO: deprecate? why do we allow this?
            for key, value in kwargs.items():
                if value is not None:
                    setattr(self, key, value)

    def set_postpone(
        self,
        result: Any = None,
        seconds: int | None = None,
    ) -> None:
        """Postpone the job for a later retry

        Write an estimated time arrival to n seconds
        later than now. Used when an retryable exception
        want to retry a job later.
        """
        self.eta = timedelta(seconds=self._get_retry_seconds(seconds))
        self.exc_name = None
        self.exc_message = None
        self.exc_info = None
        self.set_pending(result=result, reset_retry=False)

    def postpone(self, result=None, seconds=None):
        # TODO: deprecation warning
        return self.set_postpone(result=result, seconds=seconds)

    def __repr__(self):
        return f"<Job {self.uuid}, priority:{self.priority}"

    def _get_retry_seconds(self, seconds: int | None = None) -> int:
        return self.job_config.retry_seconds(self.retry, seconds=seconds)

    def _no_env_compat(self, name: str, replacement: str):
        warnings.warn(
            f"{name} is deprecated and will be removed in the next major "
            f"version, use {replacement} instead",
            DeprecationWarning,
            stacklevel=3,
        )
        raise RuntimeError(
            f"Job has no environment. {name} is deprecated, "
            f"use {replacement} instead"
        )

    def store(self):
        """Deprecated: use JobStore(env).enqueue(...) or JobStore(env).save(job)"""
        self._no_env_compat(
            "store", "JobStore(env).enqueue(...) or JobStore(env).save(job)"
        )

    def add_lock_record(self) -> None:
        """Deprecated: use ``JobStore(env).add_lock_record(job)``."""
        self._no_env_compat("Job.add_lock_record", "JobStore(env).add_lock_record(job)")

    def lock(self) -> bool:
        """Deprecated: use ``JobStore(env).lock(job)``."""
        self._no_env_compat("Job.lock", "JobStore(env).lock(job)")

    def enqueue_waiting(self) -> None:
        """Deprecated: use ``JobStore(env).enqueue_waiting(job)``."""
        self._no_env_compat("Job.enqueue_waiting", "JobStore(env).enqueue_waiting(job)")

    def cancel_dependent_jobs(self) -> None:
        """Deprecated: use ``JobStore(env).cancel_dependent_jobs(job)``."""
        self._no_env_compat(
            "Job.cancel_dependent_jobs", "JobStore(env).cancel_dependent_jobs(job)"
        )

    def _store_values(self, create: bool = False) -> dict:
        """Deprecated: use ``JobStore(env)._store_values(job)``."""
        self._no_env_compat("Job._store_values", "JobStore(env)._store_values(job)")


class JobCompat:
    """Deprecated compatibility shim"""

    # TODO
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
        job_spec = JobSpec.from_call(func, args, kwargs)
        self.func = func
        self.recordset = job_spec.recordset
        self.args = job_spec.args
        self.kwargs = job_spec.kwargs
        self.model_name = job_spec.model_name
        self.method_name = job_spec.method_name
        self.priority = priority if priority is not None else DEFAULT_PRIORITY
        self._eta = _normalize_eta(eta)
        self.max_retries = DEFAULT_MAX_RETRIES if max_retries is None else max_retries
        self.description = description
        self.channel = channel
        self.identity_key = identity_key
        self._uuid = job_uuid
        func_model = self.recordset.env["queue.job.function"].sudo()
        self.job_config = func_model.job_config(
            func_model.job_function_name(self.model_name, self.method_name)
        )
        self.state = PENDING
        self.retry = 0
        self.result = None
        self.exc_name = None
        self.exc_message = None
        self.exc_info = None
        self.date_created = datetime.now()
        self.date_enqueued = None
        self.date_started = None
        self.date_done = None
        self.date_cancelled = None
        self.worker_pid = None
        self._stored_job = None


class JobStore:
    """Persistence of jobs

    The only writer of ``queue.job`` for any creation or updates.

    Records are stored with the environment / transaction given
    at construction.
    """

    def __init__(self, env: odoo.api.Environment):
        self.env = env

    def enqueue(
        self,
        func,
        args: Sequence | None = None,
        kwargs: dict | None = None,
        *,
        priority: int | None = None,
        eta=None,
        max_retries: int | None = None,
        description: str | None = None,
        channel: str | None = None,
        identity_key: "str | Callable | None" = None,
        job_uuid: str | None = None,
        graph_uuid: str | None = None,
        depends_on_uuids: "Sequence[str] | set[str] | None" = None,
        reverse_depends_on_uuids: "Sequence[str] | set[str] | None" = None,
        state: str = PENDING,
    ) -> "Job | JobCompat":
        """Create the ``queue_job`` record of a method call, return its Job.

        The place where jobs are born. The delay() calls end up here.
        """
        job_spec = JobSpec.from_call(func, args, kwargs)
        recordset = job_spec.recordset
        env = recordset.env

        func_model = env["queue.job.function"].sudo()
        job_function_name = func_model.job_function_name(
            job_spec.model_name, job_spec.method_name
        )
        job_config = func_model.job_config(job_function_name)

        if not isinstance(identity_key, str | None):
            identity_key = identity_key(job_spec)

        if description is None:
            description = (
                func.__doc__ and func.__doc__.splitlines()[0].strip()
            ) or f"{job_spec.model_name}.{job_spec.method_name}"

        str_args = [repr(arg) for arg in job_spec.args]
        str_args += [f"{key}={val!r}" for key, val in job_spec.kwargs.items()]
        func_string = f"{recordset!r}.{job_spec.method_name}({', '.join(str_args)})"

        if "company_id" in env.context:
            company_id = env.context["company_id"]
        else:
            company_id = env.company.id

        vals = {
            "uuid": job_uuid or str(uuid.uuid4()),
            "graph_uuid": graph_uuid,
            "state": state,
            "priority": DEFAULT_PRIORITY if priority is None else priority,
            "retry": 0,
            "max_retries": (
                DEFAULT_MAX_RETRIES if max_retries is None else max_retries
            ),
            "user_id": env.uid,
            "company_id": company_id,
            "channel": channel or job_config.channel,
            "name": description,
            "func_string": func_string,
            "date_created": datetime.now(),
            "model_name": job_spec.model_name,
            "method_name": job_spec.method_name,
            "job_function_id": job_config.job_function_id,
            "channel_method_name": job_function_name,
            "records": recordset,
            "args": job_spec.args,
            "kwargs": job_spec.kwargs,
            "eta": _normalize_eta(eta) or False,
            "identity_key": identity_key or False,
            "dependencies": {
                "depends_on": sorted(depends_on_uuids or ()),
                "reverse_depends_on": sorted(reverse_depends_on_uuids or ()),
            },
        }

        hook_job_spec = job_spec._replace(uuid=vals["uuid"], state=state)
        # TODO: breaking as the hooks do not have a full job but a job spec
        vals_from_model = self._values_from_model(hook_job_spec)
        # Sanitize values: make sure you cannot screw core values
        vals.update({k: v for k, v in vals_from_model.items() if k not in vals})

        job_model = self.env["queue.job"].sudo()
        record = job_model.with_context(
            _job_edit_sentinel=job_model.EDIT_SENTINEL
        ).create(vals)
        return Job(record)

    def save(self, job: "Job") -> None:
        """Update the database record of ``job``"""
        self._maybe_transition_wait_dependencies(job)

        job_model = self.env["queue.job"].sudo()

        db_record = job_model.search([("uuid", "=", job.uuid)], limit=1)
        if not db_record:
            _logger.warning(
                "job %s not saved: its record does no longer exist", job.uuid
            )
            return
        self._write_record(db_record, job, self._all_values(job))

    def save_state(self, job: "Job", expected_states: Sequence[str]) -> bool:
        """Persist the current state of ``job`` if the job matches the expected states

        The guard takes a row lock making the check and the write atomic: a
        competing transition waits on the lock and then sees the new state.

        What the expected_states guards protects, considering odoo uses
        REPEATABLE READ isolation: The execution of a job crosses transaction
        boundaries, with several commits. The in-memory state of a job may
        be outdated compared to the actual db state.

        Return True when the row was written, False when the job was not
        in one of ``expected_states`` anymore.
        """
        self._maybe_transition_wait_dependencies(job)

        # the raw locking SELECT bypasses the ORM: flush any pending
        # state writes first
        self.env["queue.job"].flush_model()
        self.env.cr.execute(
            "SELECT id FROM queue_job WHERE uuid = %s AND state IN %s "
            "FOR NO KEY UPDATE",
            (job.uuid, tuple(expected_states)),
        )
        row = self.env.cr.fetchone()
        if not row:
            _logger.warning(
                "state '%s' not saved for job %s: the job is not in "
                "state(s) %s anymore (transitioned concurrently or deleted)",
                job.state,
                job.uuid,
                ", ".join(expected_states),
            )
            return False
        record = self.env["queue.job"].sudo().browse(row[0])
        self._write_record(record, job, self._state_values(job))
        return True

    def _maybe_transition_wait_dependencies(self, job: "Job") -> None:
        """Transition to wait dependencies unless of pending if still waiting

        A pending job with unfinished parents waits for them.
        """
        if job.state != PENDING or not job._depends_on_uuids:
            return
        unfinished = (
            self.env["queue.job"]
            .sudo()
            .search_count(
                [
                    ("uuid", "in", job._depends_on_uuids),
                    ("state", "!=", DONE),
                ],
                limit=1,
            )
        )
        if unfinished:
            job.state = WAIT_DEPENDENCIES

    def _write_record(
        self, db_record: odoo.models.BaseModel, job: "Job", vals: dict
    ) -> None:
        """Write the state values of ``job`` on its record."""
        vals_from_model = self._values_from_model(job)
        # Sanitize values: make sure you cannot screw core values
        vals.update({k: v for k, v in vals_from_model.items() if k not in vals})
        # The sentinel is used to prevent edition sensitive fields (such as
        # method_name) from RPC methods.
        db_record.with_context(_job_edit_sentinel=db_record.EDIT_SENTINEL).write(vals)

    def _state_values(self, job: "Job") -> dict:
        """The fields saved by save_state.

        These are only the fields mutated by the various ``set_done``, ``set_failed``,
        ... methods.
        """
        return {
            "state": job.state,
            "retry": job.retry,
            "result": str(job.result) if job.result else False,
            "exc_name": job.exc_name,
            "exc_message": job.exc_message,
            "exc_info": job.exc_info,
            "date_enqueued": job.date_enqueued or False,
            "date_started": job.date_started or False,
            "date_done": job.date_done or False,
            "exec_time": job.exec_time or False,
            "date_cancelled": job.date_cancelled or False,
            "eta": job.eta or False,
            "worker_pid": job.worker_pid,
        }

    def _all_values(self, job: "Job") -> dict:
        """The whole mutable data of the job."""
        vals = self._state_values(job)
        vals.update(
            {
                "priority": job.priority,
                "max_retries": job.max_retries,
                "company_id": job.company_id,
                "identity_key": job.identity_key or False,
                "graph_uuid": job.graph_uuid,
                "dependencies": {
                    "depends_on": sorted(job.depends_on_uuids),
                    "reverse_depends_on": sorted(job.reverse_depends_on_uuids),
                },
            }
        )
        return vals

    def _values_from_model(self, job: "Job | JobSpec") -> dict:
        """Additional values contributed by the model's hooks."""
        vals = {}
        if job.model_name not in self.env:
            # the model of the job is gone (uninstalled module): state
            # control must keep working, and there is no hook to call
            return vals
        model = self.env[job.model_name]
        value_handlers_candidates = (
            "_job_store_values_for_" + job.method_name,
            "_job_store_values",
        )
        for candidate in value_handlers_candidates:
            handler = getattr(model, candidate, None)
            if handler is not None:
                vals = handler(job)
        return vals

    def add_lock_record(self, job: "Job") -> None:
        """Create the row locked while the job is being performed."""
        self.env.cr.execute(
            """
            INSERT INTO
                queue_job_lock (id, queue_job_id)
            SELECT
                id, id
            FROM
                queue_job
            WHERE
                uuid = %s
            ON CONFLICT(id)
            DO NOTHING;
        """,
            [job.uuid],
        )

    def lock(self, job: "Job") -> bool:
        """Lock the row of the job being performed.

        Return False when the job cannot be locked: it is not in STARTED
        state or it is already locked by another worker.
        """
        self.env.cr.execute(
            """
            SELECT
                *
            FROM
                queue_job_lock
            WHERE
                queue_job_id in (
                    SELECT
                        id
                    FROM
                        queue_job
                    WHERE
                        uuid = %s
                        AND state = %s
                )
            FOR NO KEY UPDATE SKIP LOCKED;
        """,
            [job.uuid, STARTED],
        )

        # 1 job should be locked
        return bool(self.env.cr.fetchall())

    def record_with_same_identity_key(self, identity_key: str) -> odoo.models.BaseModel:
        """A pending job record with this identity key, if any."""
        return (
            self.env["queue.job"]
            .sudo()
            .search(
                [
                    ("identity_key", "=", identity_key),
                    ("state", "in", [WAIT_DEPENDENCIES, PENDING, ENQUEUED]),
                ],
                limit=1,
            )
        )

    _DEPENDENT_JOBS_QUERY = """
            UPDATE queue_job
            SET state = %s
            FROM (
            SELECT child.id, array_agg(parent.state) as parent_states
            FROM queue_job job
            JOIN LATERAL
              json_array_elements_text(
                  job.dependencies::json->'reverse_depends_on'
              ) child_deps ON true
            JOIN queue_job child
            ON child.graph_uuid = job.graph_uuid
            AND child.uuid = child_deps
            JOIN LATERAL
                json_array_elements_text(
                  child.dependencies::json->'depends_on'
                ) parent_deps ON true
            JOIN queue_job parent
            ON parent.graph_uuid = job.graph_uuid
            AND parent.uuid = parent_deps
            WHERE job.uuid = %s
            GROUP BY child.id
            ) jobs
            WHERE
            queue_job.id = jobs.id
            AND %s = ALL(jobs.parent_states)
            AND state = %s;
        """

    def enqueue_waiting(self, job: "Job") -> None:
        """Set to pending the dependent jobs whose parents are all done."""
        self.env["queue.job"].flush_model()
        self.env.cr.execute(
            self._DEPENDENT_JOBS_QUERY, (PENDING, job.uuid, DONE, WAIT_DEPENDENCIES)
        )
        self.env["queue.job"].invalidate_model(["state"])

    def cancel_dependent_jobs(self, job: "Job") -> None:
        """Cancel the dependent jobs whose parents are all cancelled."""
        self.env["queue.job"].flush_model()
        self.env.cr.execute(
            self._DEPENDENT_JOBS_QUERY,
            (CANCELLED, job.uuid, CANCELLED, WAIT_DEPENDENCIES),
        )
        self.env["queue.job"].invalidate_model(["state"])


def _is_model_method(func):
    return inspect.ismethod(func) and isinstance(
        func.__self__.__class__, odoo.models.MetaModel
    )
