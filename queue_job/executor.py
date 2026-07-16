# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2013-2016 Camptocamp SA
# Copyright 2026 QoQa Services SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import random
import time
import traceback
from collections.abc import Sequence
from contextlib import contextmanager
from io import StringIO

from psycopg2 import OperationalError, errorcodes

from odoo import api
from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY
from odoo.tools import config

from .exception import RetryableJobError
from .job import ENQUEUED, Job, JobStore

_logger = logging.getLogger(__name__)

PG_RETRY = 5  # seconds

DEPENDS_MAX_TRIES_ON_CONCURRENCY_FAILURE = 5


@contextmanager
def _prevent_commit(cr):
    """Context manager to prevent commits on a cursor.

    Commiting while the job is not finished would release the job lock, causing
    it to be started again by the dead jobs requeuer.
    """

    def forbidden_commit(*args, **kwargs):
        raise RuntimeError(
            "Commit is forbidden in queue jobs. "
            'You may want to enable the "Allow Commit" option on the Job '
            "Function. Alternatively, if the current job is a cron running as "
            "queue job, you can modify it to run as a normal cron. More details on: "
            "https://github.com/OCA/queue/wiki/Upgrade-warning:-commits-inside-jobs"
        )

    original_commit = cr.commit
    cr.commit = forbidden_commit
    try:
        yield
    finally:
        cr.commit = original_commit


class JobExecutor:
    def __init__(self, env: api.Environment, job_uuid: str):
        self.job_uuid = job_uuid
        self.control_env = env

    def run(self):
        job = self.acquire()
        if not job:
            return
        self.run_job(job)

    def acquire(self) -> Job | None:
        """Acquire the job for execution.

        - make sure it is in ENQUEUED state
        - mark it as STARTED and commit the state change
        - acquire the job lock

        If successful, return the Job instance, otherwise return None. This
        function may fail to acquire the job is not in the expected state or is
        already locked by another worker.
        """
        self.control_env.cr.execute(
            "SELECT uuid FROM queue_job WHERE uuid=%s AND state=%s "
            "FOR NO KEY UPDATE SKIP LOCKED",
            (self.job_uuid, ENQUEUED),
        )
        if not self.control_env.cr.fetchone():
            _logger.warning(
                "was requested to run job %s, but it does not exist, "
                "or is not in state %s, or is being handled by another worker",
                self.job_uuid,
                ENQUEUED,
            )
            return None
        # TODO: lazy-load recordset, args, kwargs etc.
        job = Job.load(self.control_env, self.job_uuid)
        assert job and job.state == ENQUEUED
        job.set_started()
        job_store = JobStore(self.control_env)
        job_store.add_lock_record(job)
        job_store.save_state(job, expected_states=(ENQUEUED,))
        if not config["test_enable"]:
            self.control_env.cr.commit()  # pylint: disable=invalid-commit
        else:
            self.control_env.cr.flush()
        if not job_store.lock(job):
            _logger.warning(
                "was requested to run job %s, but it could not be locked",
                self.job_uuid,
            )
            return None
        return job

    def run_job(self, job):
        initial_state = job.state
        try:
            try:
                self.try_perform_job(job)
            except OperationalError as err:
                # Automatically retry the typical transaction serialization
                # errors
                if err.pgcode not in PG_CONCURRENCY_ERRORS_TO_RETRY:
                    raise

                _logger.debug("%s OperationalError, postponed", job)
                raise RetryableJobError(err.pgerror, seconds=PG_RETRY) from err

        except RetryableJobError as err:
            # delay the job later, requeue
            self._record_retry(job, err, (initial_state,))
            _logger.debug("%s postponed", job)
            return

        except Exception as orig_exception:
            self._record_failure(job, orig_exception, (initial_state,))
            raise

        self._enqueue_dependent_jobs(job)

    def try_perform_job(self, job):
        """Try to perform the job, mark it done and commit if successful."""
        _logger.debug("%s started", job)
        # TODO: clarify which env has "control" over the job state and
        # which env "executes" the job method
        # We can use a JobStore with the env that changes the job state,
        # that will be the "control" env, and use an "execution" env
        # for the actual run of the job.
        #
        # TODO: implement the normal execution mode and the "isolated"
        # (allowing commits) execution mode
        execution_env = self.control_env
        job_store = JobStore(execution_env)
        initial_state = job.state

        savepoint = self.control_env.cr.savepoint(flush=False)
        try:
            with _prevent_commit(execution_env.cr):
                job.perform(execution_env)
                # Triggers any stored computed fields before calling 'set_done'
                # so that will be part of the 'exec_time'
                execution_env.flush_all()
                job.set_done()
                # when job happens without failure, the done state change is
                # done by the execution env, so it is transactional
                job_store.save_state(job, (initial_state,))
                execution_env.flush_all()
        except Exception:
            # Rollback to the savepoint so we can register the failure state
            # in the same transaction
            savepoint.close(rollback=True)
            self.control_env.clear()
            raise
        savepoint.close(rollback=False)

        if not config["test_enable"]:
            self.control_env.cr.commit()  # pylint: disable=invalid-commit
        _logger.debug("%s done", job)

    def _record_retry(
        self,
        job: Job,
        err: RetryableJobError,
        expected_states: Sequence[str],
    ) -> None:
        """Postpone the job for a later retry"""
        job.set_postpone(result=str(err), seconds=err.seconds)
        job_store = JobStore(self.control_env)
        job_store.save_state(job, expected_states)
        if not config["test_enable"]:
            self.control_env.cr.commit()

    def _record_failure(
        self,
        job: Job,
        orig_exception: Exception,
        expected_states: Sequence[str],
    ) -> None:
        """Record the failure of the job with the exception details."""
        buff = StringIO()
        traceback.print_exc(file=buff)
        traceback_txt = buff.getvalue()
        _logger.error(traceback_txt)
        job_store = JobStore(self.control_env)
        job.set_failed(**self._get_failure_values(traceback_txt, orig_exception))
        job_store.save_state(job, expected_states)
        buff.close()
        if not config["test_enable"]:
            self.control_env.cr.commit()

    def _enqueue_dependent_jobs(self, job):
        """Set the dependent jobs of a done job to pending."""
        if not job.should_check_dependents():
            return

        _logger.debug("%s enqueue depends started", job)
        tries = 0
        while True:
            try:
                with self.control_env.cr.savepoint():
                    job_store = JobStore(self.control_env)
                    job_store.enqueue_waiting(job)
            except OperationalError as err:
                # Automatically retry the typical transaction serialization
                # errors
                if err.pgcode not in PG_CONCURRENCY_ERRORS_TO_RETRY:
                    raise
                if tries >= DEPENDS_MAX_TRIES_ON_CONCURRENCY_FAILURE:
                    _logger.error(
                        "%s, maximum number of tries reached to update dependencies",
                        errorcodes.lookup(err.pgcode),
                    )
                    raise
                wait_time = random.uniform(0.0, 2**tries)
                tries += 1
                _logger.info(
                    "%s, retry %d/%d in %.04f sec...",
                    errorcodes.lookup(err.pgcode),
                    tries,
                    DEPENDS_MAX_TRIES_ON_CONCURRENCY_FAILURE,
                    wait_time,
                )
                time.sleep(wait_time)
            else:
                break
        _logger.debug("%s enqueue depends done", job)

    @staticmethod
    def _get_failure_values(traceback_txt, orig_exception):
        """Collect relevant data from exception."""
        exception_name = orig_exception.__class__.__name__
        if hasattr(orig_exception, "__module__"):
            exception_name = orig_exception.__module__ + "." + exception_name
        exc_message = (
            orig_exception.args[0] if orig_exception.args else str(orig_exception)
        )
        return {
            "exc_info": traceback_txt,
            "exc_name": exception_name,
            "exc_message": exc_message,
        }
