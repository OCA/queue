# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2013-2016 Camptocamp SA
# Copyright 2026 QoQa Services SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import random
import time
import traceback
from contextlib import contextmanager
from io import StringIO

from psycopg2 import OperationalError, errorcodes

from odoo import api
from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY
from odoo.tools import config

from .exception import FailedJobError, RetryableJobError
from .job import ENQUEUED, Job

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
        self.env = env

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
        self.env.cr.execute(
            "SELECT uuid FROM queue_job WHERE uuid=%s AND state=%s "
            "FOR NO KEY UPDATE SKIP LOCKED",
            (self.job_uuid, ENQUEUED),
        )
        if not self.env.cr.fetchone():
            _logger.warning(
                "was requested to run job %s, but it does not exist, "
                "or is not in state %s, or is being handled by another worker",
                self.job_uuid,
                ENQUEUED,
            )
            return None
        # TODO: lazy-load recordset, args, kwargs etc.
        job = Job.load(self.env, self.job_uuid)
        assert job and job.state == ENQUEUED
        job.set_started()
        job.store()
        self.env.cr.commit()  # pylint: disable=invalid-commit
        if not job.lock():
            _logger.warning(
                "was requested to run job %s, but it could not be locked",
                self.job_uuid,
            )
            return None
        return job

    def run_job(self, job):
        def retry_postpone(job, message, seconds=None):
            job.env.clear()
            with job.in_temporary_env():
                job.postpone(result=message, seconds=seconds)
                job.set_pending(reset_retry=False)
                job.store()

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
            retry_postpone(job, str(err), seconds=err.seconds)
            _logger.debug("%s postponed", job)
            # Do not trigger the error up because we don't want an exception
            # traceback in the logs we should have the traceback when all
            # retries are exhausted
            self.env.cr.rollback()
            return

        except (FailedJobError, Exception) as orig_exception:
            buff = StringIO()
            traceback.print_exc(file=buff)
            traceback_txt = buff.getvalue()
            _logger.error(traceback_txt)
            job.env.clear()
            with job.in_temporary_env():
                vals = self._get_failure_values(traceback_txt, orig_exception)
                job.set_failed(**vals)
                job.store()
                buff.close()
            raise

        self._enqueue_dependent_jobs(job)

    def try_perform_job(self, job):
        """Try to perform the job, mark it done and commit if successful."""
        _logger.debug("%s started", job)
        # TODO: clarify which env has "control" over the job state and
        # which env "executes" the job method
        assert self.env.cr is job.env.cr
        with _prevent_commit(self.env.cr):
            job.perform()
            # Triggers any stored computed fields before calling 'set_done'
            # so that will be part of the 'exec_time'
            job.env.flush_all()
            job.set_done()
            job.store()
            job.env.flush_all()
        if not config["test_enable"]:
            self.env.cr.commit()  # pylint: disable=invalid-commit
        _logger.debug("%s done", job)

    def _enqueue_dependent_jobs(self, job):
        """Set the dependent jobs of a done job to pending."""
        if not job.should_check_dependents():
            return

        _logger.debug("%s enqueue depends started", job)
        tries = 0
        while True:
            try:
                with job.env.cr.savepoint():
                    job.enqueue_waiting()
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
