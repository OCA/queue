# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from werkzeug.exceptions import BadRequest, Forbidden

from odoo import http

from odoo.addons.queue_job.controllers.main import RunJobController


class RunJobBatchController(RunJobController):
    @staticmethod
    def _parse_int(value, default):
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _parse_float(value, default):
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @classmethod
    def _create_test_batch_jobs(
        cls,
        env,
        size,
        priority=None,
        max_retries=None,
        channel=None,
        description="Test job",
        batch_name=None,
        failure_rate=0,
        job_duration=0,
        commit_within_job=False,
        failure_retry_seconds=0,
    ):
        batch = env["queue.job.batch"].get_new_batch(batch_name or description)
        delayed_model = env["queue.job"].with_context(job_batch=batch)
        job_uuids = []

        for index in range(1, size + 1):
            job_description = description if size == 1 else f"{description} #{index}"
            delayed = delayed_model.with_delay(
                priority=priority,
                max_retries=max_retries,
                channel=channel,
                description=job_description,
            )._test_job(
                failure_rate=failure_rate,
                job_duration=job_duration,
                commit_within_job=commit_within_job,
                failure_retry_seconds=failure_retry_seconds,
            )
            job_uuids.append(delayed.db_record().uuid)

        batch.check_state()
        return batch, job_uuids

    @http.route("/queue_job/create_test_batch", type="http", auth="user")
    def create_test_batch(
        self,
        priority=None,
        max_retries=None,
        channel=None,
        description="Test job",
        batch_name=None,
        size=1,
        failure_rate=0,
        job_duration=0,
        commit_within_job=False,
        failure_retry_seconds=0,
    ):
        if not http.request.env.user.has_group("base.group_erp_manager"):
            raise Forbidden(http.request.env._("Access Denied"))

        failure_rate = self._parse_float(failure_rate, 0)
        job_duration = self._parse_float(job_duration, 0)
        if not 0 <= failure_rate <= 1:
            raise BadRequest("failure_rate must be between 0 and 1")

        size = self._parse_int(size, 1)
        priority = self._parse_int(priority, None)
        max_retries = self._parse_int(max_retries, None)
        failure_retry_seconds = self._parse_int(failure_retry_seconds, 0)

        if size < 1:
            return ""

        batch, job_uuids = self._create_test_batch_jobs(
            http.request.env,
            size=size,
            priority=priority,
            max_retries=max_retries,
            channel=channel,
            description=description,
            batch_name=batch_name,
            failure_rate=failure_rate,
            job_duration=job_duration,
            commit_within_job=commit_within_job,
            failure_retry_seconds=failure_retry_seconds,
        )
        return f"batch id: {batch.id}, jobs: {len(job_uuids)}"
