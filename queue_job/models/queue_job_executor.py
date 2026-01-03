# Copyright (c) 2026 ACSONE SA/NV (<http://acsone.eu>)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging

from odoo import api, models

from ..controllers.main import RunJobController
from ..job import Job

_logger = logging.getLogger(__name__)


class QueueJobExecutor(models.AbstractModel):
    _name = "queue.job.executor"
    _description = "Queue Job Executor"

    @api.model
    def _executor_cron_domain(self) -> list:
        model_id = self.env["ir.model"]._get("queue.job.executor").id
        return [
            ("model_id", "=", model_id),
            ("state", "=", "code"),
            ("code", "=", "model._execute_ready_jobs()"),
        ]

    @api.model
    def _ensure_executor_crons(self, capacity: int) -> None:
        """Since Odoo cron can't run cron jobs in parallel, we create several.

        `capacity` should be equal to the root channel capacity. If it's more,
        it's wasteful. If it's less, job will stay in ENQUEUED state longer than
        needed and loop back to PENDING due to the dead jobs requeuer.
        """
        if capacity < 1:
            return
        ref_cron = self.env.ref("queue_job.queue_job_executor_cron")
        ref_cron.active = True
        # remove clones
        self.env["ir.cron"].with_context(active_test=False).search(
            self._executor_cron_domain() + [("id", "!=", ref_cron.id)]
        ).unlink()
        # re-create desired number of clones
        for _i in range(1, capacity):
            ref_cron.copy()

    @api.model
    def _enable_executor_cron(self, capacity: int) -> None:
        self._ensure_executor_crons(capacity)
        self.env["ir.config_parameter"].set_param("queue_job.run_as", "cron")

    @api.model
    def _execute_job(self, job: Job) -> None:
        RunJobController._runjob(self.env, job)

    @api.model
    def _execute_ready_jobs(self) -> None:
        while job := RunJobController._acquire_job(self.env):
            _logger.debug("executor cron running queue job %s", job.uuid)
            self._execute_job(job)
