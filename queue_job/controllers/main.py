# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2013-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import random
import time
import traceback
from contextlib import contextmanager
from io import StringIO
from typing import Optional

from psycopg2 import OperationalError, errorcodes
from werkzeug.exceptions import BadRequest, Forbidden

from odoo import SUPERUSER_ID, _, api, http, tools
from odoo.modules.module import get_manifest
from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY
from odoo.tools import config

from ..delay import chain, group
from ..exception import FailedJobError, NothingToDoJob, RetryableJobError
from ..job import ENQUEUED, Job

_logger = logging.getLogger(__name__)

PG_RETRY = 5  # seconds

DEPENDS_MAX_TRIES_ON_CONCURRENCY_FAILURE = 5

MODULES_OUTDATED_POSTPONE_SECONDS = 15
INSTALL_IN_PROGRESS_POSTPONE_SECONDS = 15

# How long a "is this worker's module code up to date" verdict is cached before
# being recomputed, per database (a single process can serve several). Keeps a
# busy jobrunner from re-querying ir.module.module on every single job dispatch.
MODULES_UP_TO_DATE_CACHE_SECONDS = 5
_modules_up_to_date_cache = {}  # dbname -> (checked_at, outdated: bool)


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


class RunJobController(http.Controller):
    @classmethod
    def _acquire_job(cls, env: api.Environment, job_uuid: str) -> Optional[Job]:
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
        # TODO refactor, the relation between env and job.env is not clear
        assert env.cr is job.env.cr
        with _prevent_commit(env.cr):
            job.perform()
            # Triggers any stored computed fields before calling 'set_done'
            # so that will be part of the 'exec_time'
            env.flush_all()
            job.set_done()
            job.store()
            env.flush_all()
        if not config["test_enable"]:
            env.cr.commit()
        _logger.debug("%s done", job)

    @classmethod
    def _install_in_progress(cls, env):
        """True while any module is marked to be installed/upgraded/removed.

        Same guard core already applies to cron jobs
        (ir_cron._check_modules_state): while an install/upgrade is running
        anywhere in the cluster, module states sit at 'to install'/'to
        upgrade'/'to remove' in the database, and only flip back once the
        operation completes (or core's reset_modules_state() clears them on
        failure). Jobs executed during that window may run with code that
        does not yet match what the database will end up recording -- a
        module's own 'installed' state and latest_version are only committed
        near the end of its install, but data/hooks that ran earlier in the
        same install (e.g. a post_init_hook enqueuing a job) may already be
        committed and dispatchable. _worker_is_outdated() has nothing to
        compare against in that window (the module isn't even marked
        installed yet); this check covers exactly that gap.

        Deliberately not cached like _worker_is_outdated(): the whole point
        is that a job committed by a post_init_hook becomes visible in the
        same commit as the pending module state, so a fresh read makes this
        check exact. A TTL would reopen the race for its duration. The query
        is one cheap aggregate over ir_module_module.

        Pending states older than
        queue_job.install_in_progress_timeout_minutes (default 60) are
        treated as abandoned (e.g. modules left marked by a crashed/killed
        process) and ignored, with a warning logged, rather than freezing
        job processing forever. Disable the whole check with the
        queue_job.check_install_in_progress system parameter.
        """
        icp = env["ir.config_parameter"].sudo()
        if icp.get_param("queue_job.check_install_in_progress", "True") == "False":
            return False

        timeout_minutes = int(
            icp.get_param("queue_job.install_in_progress_timeout_minutes", "60")
        )
        env.cr.execute(
            """
            SELECT COUNT(*),
                   MAX(COALESCE(write_date, create_date))
                       >= (now() AT TIME ZONE 'UTC') - %s * interval '1 minute'
            FROM ir_module_module
            WHERE state IN ('to install', 'to upgrade', 'to remove')
            """,
            (timeout_minutes,),
        )
        pending, fresh = env.cr.fetchone()
        if not pending:
            return False
        if not fresh:
            _logger.warning(
                "%d module(s) have been marked to install/upgrade/remove for "
                "more than %d minutes; assuming an abandoned operation and "
                "resuming job processing",
                pending,
                timeout_minutes,
            )
            return False
        # Only reached while an install is ACTIVELY in progress (pending &
        # fresh) -- the common no-install case already returned False above.
        # Bust the version-check cache so the first job dispatched after the
        # install completes recomputes _worker_is_outdated() freshly instead
        # of reusing a pre-install verdict for up to
        # MODULES_UP_TO_DATE_CACHE_SECONDS.
        _modules_up_to_date_cache.pop(env.cr.dbname, None)
        return True

    @classmethod
    def _worker_is_outdated(cls, env):
        """True if this worker's own on-disk module code no longer matches
        what the database considers the currently installed version, for at
        least one installed module.

        ir.module.module.installed_version is a non-stored compute that reads
        the manifest fresh from *this process's* addons_path (get_manifest()
        is lru_cached per process, so this is cheap after the first call).
        ir.module.module.latest_version is what the module loader persisted to
        the database the last time this module was actually
        installed/upgraded (see odoo/modules/loading.py). A mismatch means
        some other process has since upgraded this module past what this
        worker is currently running -- most commonly, one worker in a
        multi-process or multi-host deployment has picked up new code and run
        an upgrade, while this one is still serving requests with the old
        code, in the window before it gets restarted (a rolling-deployment
        race). Running a job in that state risks acting on stale files/logic
        that no longer match the database.

        The result is cached briefly, per database, so a busy queue doesn't
        re-run this on every single job (see MODULES_UP_TO_DATE_CACHE_SECONDS).

        Disable via the ``queue_job.check_modules_up_to_date`` system
        parameter (set to ``"False"``); enabled by default.
        """
        icp = env["ir.config_parameter"].sudo()
        if icp.get_param("queue_job.check_modules_up_to_date", "True") == "False":
            return False

        dbname = env.cr.dbname
        now = time.monotonic()
        cached = _modules_up_to_date_cache.get(dbname)
        if cached and now - cached[0] < MODULES_UP_TO_DATE_CACHE_SECONDS:
            return cached[1]

        outdated = False
        modules = env["ir.module.module"].sudo().search([("state", "=", "installed")])
        for module in modules:
            manifest = get_manifest(module.name)
            if not manifest:
                # Can't read this module's manifest from this process's
                # addons_path (e.g. a module removed from disk but still
                # marked installed in the database) -- skip it rather than
                # treat an unreadable manifest as evidence of staleness.
                continue
            on_disk_version = manifest.get("version")
            if (
                on_disk_version
                and module.latest_version
                and on_disk_version != module.latest_version
            ):
                outdated = True
                break

        _modules_up_to_date_cache[dbname] = (now, outdated)
        return outdated

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
            with job.in_temporary_env():
                job.postpone(result=message, seconds=seconds)
                job.set_pending(reset_retry=False)
                job.store()

        if cls._install_in_progress(env):
            _logger.info(
                "%s: modules are being installed/upgraded somewhere in the "
                "cluster; postponing %ss",
                job,
                INSTALL_IN_PROGRESS_POSTPONE_SECONDS,
            )
            retry_postpone(
                job,
                "modules install in progress",
                seconds=INSTALL_IN_PROGRESS_POSTPONE_SECONDS,
            )
            if not config["test_enable"]:
                env.cr.rollback()
            return

        if cls._worker_is_outdated(env):
            _logger.info(
                "%s: this worker's module code is outdated relative to the "
                "database (likely a rolling deployment in progress); "
                "postponing %ss",
                job,
                MODULES_OUTDATED_POSTPONE_SECONDS,
            )
            retry_postpone(
                job, "worker outdated", seconds=MODULES_OUTDATED_POSTPONE_SECONDS
            )
            if not config["test_enable"]:
                env.cr.rollback()
            return

        try:
            try:
                cls._try_perform_job(env, job)
            except OperationalError as err:
                # Automatically retry the typical transaction serialization
                # errors
                if err.pgcode not in PG_CONCURRENCY_ERRORS_TO_RETRY:
                    raise

                _logger.debug("%s OperationalError, postponed", job)
                raise RetryableJobError(
                    tools.ustr(err.pgerror, errors="replace"), seconds=PG_RETRY
                ) from err

        except NothingToDoJob as err:
            if str(err):
                msg = str(err)
            else:
                msg = _("Job interrupted and set to Done: nothing to do.")
            job.set_done(msg)
            job.store()
            env.cr.commit()

        except RetryableJobError as err:
            # delay the job later, requeue
            retry_postpone(job, str(err), seconds=err.seconds)
            _logger.debug("%s postponed", job)
            # Do not trigger the error up because we don't want an exception
            # traceback in the logs we should have the traceback when all
            # retries are exhausted
            env.cr.rollback()
            return

        except (FailedJobError, Exception) as orig_exception:
            buff = StringIO()
            traceback.print_exc(file=buff)
            traceback_txt = buff.getvalue()
            _logger.error(traceback_txt)
            job.env.clear()
            with job.in_temporary_env():
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
        commit_within_job=False,
        failure_retry_seconds=0,
    ):
        """Create test jobs

        Examples of urls:

        * http://127.0.0.1:8069/queue_job/create_test_job: single job
        * http://127.0.0.1:8069/queue_job/create_test_job?size=10: a graph of 10 jobs
        * http://127.0.0.1:8069/queue_job/create_test_job?size=10&failure_rate=0.5:
          a graph of 10 jobs, half will fail

        """
        if not http.request.env.user.has_group("base.group_erp_manager"):
            raise Forbidden(_("Access Denied"))

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

        if failure_retry_seconds is not None:
            try:
                failure_retry_seconds = int(failure_retry_seconds)
            except ValueError:
                failure_retry_seconds = 0

        if size == 1:
            return self._create_single_test_job(
                priority=priority,
                max_retries=max_retries,
                channel=channel,
                description=description,
                failure_rate=failure_rate,
                job_duration=job_duration,
                commit_within_job=commit_within_job,
                failure_retry_seconds=failure_retry_seconds,
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
                commit_within_job=commit_within_job,
                failure_retry_seconds=failure_retry_seconds,
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
        commit_within_job=False,
        failure_retry_seconds=0,
    ):
        delayed = (
            http.request.env["queue.job"]
            .with_delay(
                priority=priority,
                max_retries=max_retries,
                channel=channel,
                description=description,
            )
            ._test_job(
                failure_rate=failure_rate,
                job_duration=job_duration,
                commit_within_job=commit_within_job,
                failure_retry_seconds=failure_retry_seconds,
            )
        )
        return "job uuid: %s" % (delayed.db_record().uuid,)

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
        commit_within_job=False,
        failure_retry_seconds=0,
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
                        description="%s #%d" % (description, current_count),
                    )._test_job(
                        failure_rate=failure_rate,
                        job_duration=job_duration,
                        commit_within_job=commit_within_job,
                        failure_retry_seconds=failure_retry_seconds,
                    )
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

        return "graph uuid: %s" % (
            list(root_delayable._head())[0]._generated_job.graph_uuid,
        )
