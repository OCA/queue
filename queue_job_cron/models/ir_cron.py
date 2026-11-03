# Copyright 2019 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import logging

from odoo import api, fields, models
from odoo.tools import SQL

from odoo.addons.queue_job.job import identity_exact

_logger = logging.getLogger(__name__)


class IrCron(models.Model):
    _inherit = "ir.cron"

    no_parallel_queue_job_run = fields.Boolean(
        help="Avoid parallel run. "
        "If a job of this cron is already pending, the new one will be "
        "skipped. If one is already running, the new one is postponed until "
        "it ends. By default, odoo never runs the same cron job in parallel. "
        "This option is therefore set to True by default when job is run as "
        "a queue job.",
        default=True,
    )

    run_as_queue_job = fields.Boolean(
        help="Specify if this cron should be ran as a queue job"
    )
    allow_commit = fields.Boolean(
        help="Run this cron's server action in a dedicated database cursor "
        "when executed as a queue job, allowing it to commit partial "
        "progress during execution. Incurs the overhead of an extra "
        "database connection. Only effective when 'Run as Queue Job' is "
        "enabled.",
    )
    channel_id = fields.Many2one(
        comodel_name="queue.job.channel",
        compute="_compute_run_as_queue_job",
        readonly=False,
        store=True,
        string="Channel",
    )

    @api.depends("run_as_queue_job")
    def _compute_run_as_queue_job(self):
        for cron in self:
            if cron.channel_id:
                continue
            if cron.run_as_queue_job:
                cron.channel_id = self.env.ref("queue_job_cron.channel_root_ir_cron").id
            else:
                cron.channel_id = False

    @api.onchange("run_as_queue_job")
    def _onchange_run_as_queue_job(self):
        if not self.run_as_queue_job:
            self.allow_commit = False

    def _run_job_as_queue_job(self, server_action):
        self.ensure_one()
        if self.no_parallel_queue_job_run:
            self._lock_running_cron()
        if self.allow_commit:
            with self.env.registry.cursor() as new_cr:
                new_env = self.env(cr=new_cr)
                res, deactivate, triggered = self.with_env(
                    new_env
                )._run_server_action_with_progress(server_action.with_env(new_env))
        else:
            res, deactivate, triggered = self._run_server_action_with_progress(
                server_action
            )
        if deactivate:
            # on the job cursor: the dedicated one would wait on our row lock
            self.active = False
        if triggered:
            # the cron worker skipped the triggers committed while we held the
            # row lock: wake it up once the job cursor commits
            self.env.cr.postcommit.add(self._notifydb)
        return res

    def _lock_running_cron(self):
        """Hold the cron row until the job ends, as the native cron worker
        does while it runs a cron: the worker acquires crons with
        FOR NO KEY UPDATE SKIP LOCKED, so it won't enqueue this cron again
        (e.g. from a trigger committed mid-run with allow_commit) before this
        job ends. When another run holds it, LockNotAvailable is turned into a
        postponed retry by queue_job.
        """
        self.env.cr.execute(
            SQL(
                "SELECT id FROM ir_cron WHERE id = %s FOR NO KEY UPDATE NOWAIT",
                self.id,
            ),
            log_exceptions=False,
        )

    def _run_server_action_with_progress(self, server_action):
        """Run the server action with the progress API wired as the native
        cron runner does, since _notify_progress is a no-op without a
        progress record in context. Re-trigger the cron instead of looping
        over batches.

        :return: a triple ``(result, deactivate, triggered)``, ``result``
            being the return value of the server action
        """
        cron, progress = self._add_progress()
        res = server_action.with_env(cron.env).run()
        if progress.done and progress.remaining:
            cron._trigger()
        triggered = bool(
            self.env["ir.cron.trigger"]
            .sudo()
            .search_count(
                [
                    ("cron_id", "=", self.id),
                    ("call_at", "<=", fields.Datetime.now()),
                ],
                limit=1,
            )
        )
        return res, progress.deactivate and not progress.remaining, triggered

    def method_direct_trigger(self):
        for cron in self:
            if not cron.run_as_queue_job:
                super(IrCron, cron).method_direct_trigger()
            else:
                _cron = cron.with_user(cron.user_id).with_context(
                    lastcall=cron.lastcall
                )
                _cron._delay_run_job_as_queue_job(
                    server_action=_cron.ir_actions_server_id
                )
        return True

    def _callback(self, cron_name, server_action_id):
        self.ensure_one()
        if self.run_as_queue_job:
            server_action = self.env["ir.actions.server"].browse(server_action_id)
            return self._delay_run_job_as_queue_job(server_action=server_action)
        else:
            return super()._callback(
                cron_name=cron_name, server_action_id=server_action_id
            )

    def _delay_run_job_as_queue_job(self, server_action):
        self.ensure_one()
        identity_key = None
        if self.no_parallel_queue_job_run:
            identity_key = identity_exact
        return self.with_delay(
            priority=self.priority,
            description=self.name,
            channel=self.channel_id.complete_name,
            identity_key=identity_key,
        )._run_job_as_queue_job(server_action=server_action)
