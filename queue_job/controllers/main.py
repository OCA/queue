# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2013-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import random

from werkzeug.exceptions import BadRequest, Forbidden

from odoo import SUPERUSER_ID, _, http

from ..delay import chain, group

# unused imports are kept for backward compatibility
from ..executor import (
    DEPENDS_MAX_TRIES_ON_CONCURRENCY_FAILURE,  # noqa: F401
    PG_RETRY,  # noqa: F401
    JobExecutor,
    _prevent_commit,  # noqa: F401
)

_logger = logging.getLogger(__name__)


class RunJobController(http.Controller):
    @http.route(
        "/queue_job/runjob",
        type="http",
        auth="none",
        save_session=False,
        readonly=False,
    )
    def runjob(self, db, job_uuid, **kw):
        http.request.session.db = db
        # update_env (in contrast to a local request.env(user=...)) replaces
        # the uid=None environment installed by auth="none" on the request
        # itself. On Odoo >= 19 it additionally repoints
        # transaction.default_env, which otherwise makes flushes recompute
        # stored fields with uid=None (see OCA/queue issue #922)
        http.request.update_env(user=SUPERUSER_ID)
        JobExecutor(http.request.env, job_uuid).run()
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

        return (
            f"graph uuid: {list(root_delayable._head())[0]._generated_job.graph_uuid}"
        )
