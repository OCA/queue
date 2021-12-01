# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2013-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import traceback
from io import StringIO

from psycopg2 import OperationalError
from werkzeug.exceptions import Forbidden

import odoo
from odoo import _, http, tools
from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY

from ..exception import FailedJobError, NothingToDoJob, RetryableJobError
from ..job import ENQUEUED, Job

_logger = logging.getLogger(__name__)

PG_RETRY = 5  # seconds


class RunJobController(http.Controller):
    def _try_perform_job(self, env, job):
        """Try to perform the job."""
        job.set_started()
        job.store()
        env.cr.commit()
        _logger.debug("%s started", job)

        job.perform()
        job.set_done()
        job.store()
        env["base"].flush()
        env.cr.commit()
        _logger.debug("%s done", job)

    @http.route("/queue_job/runjob", type="http", auth="none", save_session=False)
    def runjob(self, db, job_uuid, **kw):
        http.request.session.db = db
        env = http.request.env(user=odoo.SUPERUSER_ID)

        def retry_postpone(job, message, seconds=None):
            job.env.clear()
            with odoo.api.Environment.manage():
                with odoo.registry(job.env.cr.dbname).cursor() as new_cr:
                    job.env = job.env(cr=new_cr)
                    job.postpone(result=message, seconds=seconds)
                    job.set_pending(reset_retry=False)
                    job.store()
                    new_cr.commit()

        # ensure the job to run is in the correct state and lock the record
        env.cr.execute(
            "SELECT state FROM queue_job WHERE uuid=%s AND state=%s FOR UPDATE",
            (job_uuid, ENQUEUED),
        )
        if not env.cr.fetchone():
            _logger.warning(
                "was requested to run job %s, but it does not exist, "
                "or is not in state %s",
                job_uuid,
                ENQUEUED,
            )
            return ""

        job = Job.load(env, job_uuid)
        assert job and job.state == ENQUEUED

        try:
            try:
                self._try_perform_job(env, job)
            except OperationalError as err:
                # Automatically retry the typical transaction serialization
                # errors
                if err.pgcode not in PG_CONCURRENCY_ERRORS_TO_RETRY:
                    raise

                _logger.debug("%s OperationalError, postponed", job)
                raise RetryableJobError(
                    tools.ustr(err.pgerror, errors="replace"), seconds=PG_RETRY
                )

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

        except (FailedJobError, Exception) as orig_exception:
            buff = StringIO()
            traceback.print_exc(file=buff)
            traceback_txt = buff.getvalue()
            _logger.error(traceback_txt)
            job.env.clear()
            with odoo.api.Environment.manage():
                with odoo.registry(job.env.cr.dbname).cursor() as new_cr:
                    job.env = job.env(cr=new_cr)
                    vals = self._get_failure_values(job, traceback_txt, orig_exception)
                    job.set_failed(**vals)
                    job.store()
                    new_cr.commit()
                    buff.close()
            raise

        return ""

    def _get_failure_values(self, job, traceback_txt, orig_exception):
        """Collect relevant data from exception."""
        exception_name = orig_exception.__class__.__name__
        if hasattr(orig_exception, "__module__"):
            exception_name = orig_exception.__module__ + "." + exception_name
        exc_message = getattr(orig_exception, "name", str(orig_exception))
        return {
            "exc_info": traceback_txt,
            "exc_name": exception_name,
            "exc_message": exc_message,
        }

    @http.route("/queue_job/create_test_job", type="http", auth="user")
    def create_test_job(
        self, priority=None, max_retries=None, channel=None, description="Test job"
    ):
        if not http.request.env.user.has_group("base.group_erp_manager"):
            raise Forbidden(_("Access Denied"))

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

        delayed = (
            http.request.env["queue.job"]
            .with_delay(
                priority=priority,
                max_retries=max_retries,
                channel=channel,
                description=description,
            )
            ._test_job()
        )

        return delayed.db_record().uuid
