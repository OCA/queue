# Copyright 2019 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api
from odoo.tests import Form
from odoo.tests.common import TransactionCase

from odoo.addons.queue_job.controllers.main import _prevent_commit


class TestQueueJobCron(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_queue_job_cron(self):
        QueueJob = self.env["queue.job"]
        default_channel = self.env.ref("queue_job_cron.channel_root_ir_cron")
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        self.assertFalse(cron.run_as_queue_job)
        self.assertFalse(cron.allow_commit)

        cron.method_direct_trigger()
        nb_jobs = QueueJob.search_count([("name", "=", cron.name)])
        self.assertEqual(nb_jobs, 0)

        cron.write({"run_as_queue_job": True, "channel_id": default_channel.id})

        cron.method_direct_trigger()
        qjob = QueueJob.search([("name", "=", cron.name)])

        self.assertTrue(qjob)
        self.assertEqual(qjob.name, cron.name)
        self.assertEqual(qjob.priority, cron.priority)
        self.assertEqual(qjob.user_id, cron.user_id)
        self.assertEqual(qjob.channel, cron.channel_id.complete_name)

    def test_queue_job_cron_depends(self):
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        default_channel = self.env.ref("queue_job_cron.channel_root_ir_cron")
        self.assertFalse(cron.run_as_queue_job)
        cron.write({"run_as_queue_job": True})
        self.assertEqual(cron.channel_id.id, default_channel.id)

    def test_queue_job_cron_run(self):
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        IrCron = self.env["ir.cron"]
        IrCron._run_job_as_queue_job(server_action=cron.ir_actions_server_id)

    def test_queue_job_no_parallelism(self):
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        default_channel = self.env.ref("queue_job_cron.channel_root_ir_cron")
        cron.write(
            {
                "no_parallel_queue_job_run": True,
                "run_as_queue_job": True,
                "channel_id": default_channel.id,
            }
        )
        cron.method_direct_trigger()
        cron.method_direct_trigger()
        nb_jobs = self.env["queue.job"].search_count([("name", "=", cron.name)])
        self.assertEqual(nb_jobs, 1)
        cron.no_parallel_queue_job_run = False
        cron.method_direct_trigger()
        nb_jobs = self.env["queue.job"].search_count([("name", "=", cron.name)])
        self.assertEqual(nb_jobs, 2)

    def test_queue_job_cron_callback(self):
        nb_partners = self.env["res.partner"].search_count([])
        nb_jobs = self.env["queue.job"].search_count([])
        partner_model = self.env.ref("base.model_res_partner")
        action = self.env["ir.actions.server"].create(
            {
                "name": "Queue job cron callback action create partner",
                "state": "code",
                "model_id": partner_model.id,
                "crud_model_id": partner_model.id,
                "code": "model.name_create('job Cron partner')",
            }
        )
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        cron._callback("Test queue job cron", action.id)
        nb_partners_after_cron = self.env["res.partner"].search_count([])
        self.assertEqual(nb_partners_after_cron, nb_partners + 1)
        cron.write({"run_as_queue_job": True})
        cron._callback("Test queue job cron", action.id)
        nb_partners_after_cron = self.env["res.partner"].search_count([])
        self.assertEqual(nb_partners_after_cron, nb_partners + 1)
        nb_jobs_after_cron = self.env["queue.job"].search_count([])
        self.assertEqual(nb_jobs_after_cron, nb_jobs + 1)

    def test_queue_job_cron_allow_commit_reset_onchange(self):
        """Unchecking 'Run as Queue Job' in the form clears allow_commit."""
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        with Form(cron) as cron_form:
            cron_form.run_as_queue_job = True
            cron_form.allow_commit = True
            cron_form.run_as_queue_job = False
            self.assertFalse(cron_form.allow_commit)

    def test_queue_job_cron_commit_forbidden_without_allow_commit(self):
        """Without allow_commit, the job runs on self.cr - the same
        cursor _try_perform_job protects with _prevent_commit for any
        real job execution - so an explicit commit() inside the server
        action must raise, exactly as it would for a normal job."""
        partner_model = self.env.ref("base.model_res_partner")
        action = self.env["ir.actions.server"].create(
            {
                "name": "Queue job cron forbidden commit",
                "state": "code",
                "model_id": partner_model.id,
                "crud_model_id": partner_model.id,
                "code": "env.cr.commit()",
            }
        )
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        self.assertFalse(cron.allow_commit)
        with _prevent_commit(self.cr):
            with self.assertRaisesRegex(ValueError, "Commit is forbidden"):
                cron._run_job_as_queue_job(server_action=action)

    def test_queue_job_cron_allow_commit_bypasses_forbidden_commit(self):
        """allow_commit runs on its own dedicated cursor, so it's
        unaffected by _prevent_commit patching self.cr - this is the
        whole reason the option exists."""
        partner_model = self.env.ref("base.model_res_partner")
        with self.registry.cursor() as setup_cr:
            setup_env = api.Environment(setup_cr, self.env.uid, {})
            action = setup_env["ir.actions.server"].create(
                {
                    "name": "Queue job cron allow_commit bypasses forbidden commit",
                    "state": "code",
                    "model_id": partner_model.id,
                    "crud_model_id": partner_model.id,
                    "code": "env.cr.commit()",
                }
            )
            action_id = action.id
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        cron.write({"allow_commit": True})
        action = self.env["ir.actions.server"].browse(action_id)
        with _prevent_commit(self.cr):
            cron._run_job_as_queue_job(server_action=action)  # must not raise
