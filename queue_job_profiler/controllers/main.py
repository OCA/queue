# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tools.profiler import Profiler

from odoo.addons.queue_job.controllers.main import RunJobController as BaseController


class RunJobController(BaseController):
    def _try_perform_job(self, env, job):
        if self._profiler_is_enabled(env, job):
            return self._profiler_perform_job(env, job)
        return super()._try_perform_job(env, job)

    def _profiler_is_enabled(self, env, job):
        func_id = job.job_config.job_function_id
        if not func_id:
            return False
        job_function = env["queue.job.function"].browse(func_id)
        return job_function.is_profiling_enabled()

    def _profiler_perform_job(self, env, job):
        with self._profiler_get(env, job):
            result = super()._try_perform_job(env, job)
        return result

    def _profiler_get(self, env, job):
        func_id = job.job_config.job_function_id
        if not func_id:
            return None
        job_function = env["queue.job.function"].browse(func_id)
        return Profiler(
            description=job_function._profile_make_name(job),
            profile_session=f"{env.user.name} (uid={env.user.id})",
        )
