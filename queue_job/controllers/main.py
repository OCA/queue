# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2013-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import random
import time
import traceback
from io import StringIO

from psycopg2 import OperationalError, errorcodes
from werkzeug.exceptions import BadRequest, Forbidden

from odoo import SUPERUSER_ID, api, http
from odoo.modules.registry import Registry
from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY

from ..delay import chain, group
from ..exception import FailedJobError, RetryableJobError
from ..job import ENQUEUED, Job

_logger = logging.getLogger(__name__)

PG_RETRY = 5  # seconds

DEPENDS_MAX_TRIES_ON_CONCURRENCY_FAILURE = 5


class RunJobController(http.Controller):
    @classmethod
    def _acquire_job(cls, env: api.Environment, job_uuid: str) -> Job | None:
        """Acquire a job for execution.

        - make sure it is in ENQUEUED state
        - mark it as STARTED and commit the state change
        - acquire the job lock

        If successful, return the Job instance, otherwise return None. This
        function may fail to acquire the job is not in the expected state or is
        already locked by another worker.
        """
        env.cr.execute(
            "SELECT uuid FROM queue_job WHERE uuid=%s AND state=%s "
            "FOR NO KEY UPDATE SKIP LOCKED",
            (job_uuid, ENQUEUED),
        )
        if not env.cr.fetchone():
            _logger.warning(
                "was requested to run job %s, but it does not exist, "
                "or is not in state %s, or is being handled by another worker",
                job_uuid,
                ENQUEUED,
            )
            return None
        job = Job.load(env, job_uuid)
        assert job and job.state == ENQUEUED
        job.set_started()
        job.store()
        env.cr.commit()
        if not job.lock():
            _logger.warning(
                "was requested to run job %s, but it could not be locked",
                job_uuid,
            )
            return None
        return job

    @classmethod
    def _try_perform_job(cls, env, job):
        """Try to perform the job, mark it done and commit if successful."""
        _logger.debug("%s started", job)
        job.perform()
        # Triggers any stored computed fields before calling 'set_done'
        # so that will be part of the 'exec_time'
        env.flush_all()
        job.set_done()
        job.store()
        env.flush_all()
        env.cr.commit()
        _logger.debug("%s done", job)

    @classmethod
    def _enqueue_dependent_jobs(cls, env, job):
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

    @classmethod
    def _runjob(cls, env: api.Environment, job: Job) -> None:
        def retry_postpone(job, message, seconds=None):
            job.env.clear()
            with Registry(job.env.cr.dbname).cursor() as new_cr:
                job.env = api.Environment(new_cr, SUPERUSER_ID, {})
                job.postpone(result=message, seconds=seconds)
                job.set_pending(reset_retry=False)
                job.store()

        try:
            try:
                cls._try_perform_job(env, job)
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
            env.cr.rollback()

        except (FailedJobError, Exception) as orig_exception:
            buff = StringIO()
            traceback.print_exc(file=buff)
            traceback_txt = buff.getvalue()
            _logger.error(traceback_txt)
            job.env.clear()
            with Registry(job.env.cr.dbname).cursor() as new_cr:
                job.env = job.env(cr=new_cr)
                vals = cls._get_failure_values(job, traceback_txt, orig_exception)
                job.set_failed(**vals)
                job.store()
                buff.close()
            raise

        _logger.debug("%s enqueue depends started", job)
        cls._enqueue_dependent_jobs(env, job)
        _logger.debug("%s enqueue depends done", job)

    @classmethod
    def _get_failure_values(cls, job, traceback_txt, orig_exception):
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

    @http.route(
        "/queue_job/runjob",
        type="http",
        auth="none",
        save_session=False,
        readonly=False,
    )
    def runjob(self, db, job_uuid, **kw):
        http.request.session.db = db
        env = http.request.env(user=SUPERUSER_ID)
        job = self._acquire_job(env, job_uuid)
        if not job:
            return ""
        self._runjob(env, job)
        return ""

    # flake8: noqa: C901
    @http.route("/queue_job/create_test_job", type="http", auth="user")
    def create_test_job(
        self,
        priority=None,
        max_retries=None,
        channel=None,
        description="Test job",
        size=1,
        failure_rate=0,
        job_duration=0,
    ):
        if not http.request.env.user.has_group("base.group_erp_manager"):
            raise Forbidden(http.request.env._("Access Denied"))

        if failure_rate is not None:
            try:
                failure_rate = float(failure_rate)
            except (ValueError, TypeError):
                failure_rate = 0

        if job_duration is not None:
            try:
                job_duration = float(job_duration)
            except (ValueError, TypeError):
                job_duration = 0

        if not (0 <= failure_rate <= 1):
            raise BadRequest("failure_rate must be between 0 and 1")

        if size is not None:
            try:
                size = int(size)
            except (ValueError, TypeError):
                size = 1

        if priority is not None:
            try:
                priority = int(priority)
            except ValueError:
                priority = None

        if max_retries is not None:
            try:
                max_retries = int(max_retries)
            except ValueError:
                max_retries = None

        if size == 1:
            return self._create_single_test_job(
                priority=priority,
                max_retries=max_retries,
                channel=channel,
                description=description,
                failure_rate=failure_rate,
                job_duration=job_duration,
            )

        if size > 1:
            return self._create_graph_test_jobs(
                size,
                priority=priority,
                max_retries=max_retries,
                channel=channel,
                description=description,
                failure_rate=failure_rate,
                job_duration=job_duration,
            )
        return ""

    def _create_single_test_job(
        self,
        priority=None,
        max_retries=None,
        channel=None,
        description="Test job",
        size=1,
        failure_rate=0,
        job_duration=0,
    ):
        delayed = (
            http.request.env["queue.job"]
            .with_delay(
                priority=priority,
                max_retries=max_retries,
                channel=channel,
                description=description,
            )
            ._test_job(failure_rate=failure_rate, job_duration=job_duration)
        )
        return f"job uuid: {delayed.db_record().uuid}"

    TEST_GRAPH_MAX_PER_GROUP = 5

    def _create_graph_test_jobs(
        self,
        size,
        priority=None,
        max_retries=None,
        channel=None,
        description="Test job",
        failure_rate=0,
        job_duration=0,
    ):
        model = http.request.env["queue.job"]
        current_count = 0

        possible_grouping_methods = (chain, group)

        tails = []  # we can connect new graph chains/groups to tails
        root_delayable = None
        while current_count < size:
            jobs_count = min(
                size - current_count, random.randint(1, self.TEST_GRAPH_MAX_PER_GROUP)
            )

            jobs = []
            for __ in range(jobs_count):
                current_count += 1
                jobs.append(
                    model.delayable(
                        priority=priority,
                        max_retries=max_retries,
                        channel=channel,
                        description=f"{description} #{current_count}",
                    )._test_job(failure_rate=failure_rate, job_duration=job_duration)
                )

            grouping = random.choice(possible_grouping_methods)
            delayable = grouping(*jobs)
            if not root_delayable:
                root_delayable = delayable
            else:
                tail_delayable = random.choice(tails)
                tail_delayable.on_done(delayable)
            tails.append(delayable)

        root_delayable.delay()

        return (
            f"graph uuid: {list(root_delayable._head())[0]._generated_job.graph_uuid}"
        )
