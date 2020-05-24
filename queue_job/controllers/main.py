# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2013-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import traceback
from io import StringIO

from psycopg2 import OperationalError

import odoo
from odoo import _, http, tools
from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY

from ..job import Job, ENQUEUED
from ..exception import (NoSuchJobError,
                         NotReadableJobError,
                         RetryableJobError,
                         FailedJobError,
                         NothingToDoJob)

_logger = logging.getLogger(__name__)

PG_RETRY = 5  # seconds


class RunJobController(http.Controller):

    def _load_job(self, env, job_uuid):
        """Reload a job from the backend"""
        try:
            job = Job.load(env, job_uuid)
        except NoSuchJobError:
            # just skip it
            job = None
        except NotReadableJobError:
            _logger.exception('Could not read job: %s', job_uuid)
            raise
        return job

    def _try_perform_job(self, env, job):
        """Try to perform the job."""

        # if the job has been manually set to DONE or PENDING,
        # or if something tries to run a job that is not enqueued
        # before its execution, stop
        if job.state != ENQUEUED:
            _logger.warning('job %s is in state %s '
                            'instead of enqueued in /runjob',
                            job.uuid, job.state)
            return

        # TODO: set_started should be done atomically with
        #       update queue_job set=state=started
        #       where state=enqueid and id=
        job.set_started()
        job.store()
        http.request.env.cr.commit()

        _logger.debug('%s started', job)
        job.perform()
        job.set_done()
        job.store()
        http.request.env.cr.commit()
        _logger.debug('%s done', job)

    @http.route('/queue_job/session', type='http', auth="none")
    def session(self):
        """Used by the jobrunner to spawn a session

        The queue jobrunner uses anonymous sessions when it calls
        ``/queue_job/runjob``.  To avoid having thousands of anonymous
        sessions, before running jobs, it creates a ``requests.Session``
        and does a GET on ``/queue_job/session``, providing it a cookie
        which will be used for subsequent calls to runjob.
        """
        return ''

    @http.route('/queue_job/runjob', type='http', auth='none')
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

        job = self._load_job(env, job_uuid)
        if job is None:
            return ""
        env.cr.commit()

        try:
            try:
                self._try_perform_job(env, job)
            except OperationalError as err:
                # Automatically retry the typical transaction serialization
                # errors
                if err.pgcode not in PG_CONCURRENCY_ERRORS_TO_RETRY:
                    raise

                retry_postpone(job, tools.ustr(err.pgerror, errors='replace'),
                               seconds=PG_RETRY)
                _logger.debug('%s OperationalError, postponed', job)

        except NothingToDoJob as err:
            if str(err):
                msg = str(err)
            else:
                msg = _('Job interrupted and set to Done: nothing to do.')
            job.set_done(msg)
            job.store()
            env.cr.commit()

        except RetryableJobError as err:
            # delay the job later, requeue
            retry_postpone(job, str(err), seconds=err.seconds)
            _logger.debug('%s postponed', job)

        except (FailedJobError, Exception):
            buff = StringIO()
            traceback.print_exc(file=buff)
            _logger.error(buff.getvalue())
            job.env.clear()
            with odoo.api.Environment.manage():
                with odoo.registry(job.env.cr.dbname).cursor() as new_cr:
                    job.env = job.env(cr=new_cr)
                    job.set_failed(exc_info=buff.getvalue())
                    job.store()
                    new_cr.commit()
            raise

        return ""
