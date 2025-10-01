# Copyright 2019 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import TransactionCase


class TestQueueJobCron(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_queue_job_cron(self):
        default_channel = self.env.ref("queue_job_cron.channel_root_ir_cron")
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        self.assertFalse(cron.run_as_queue_job)

        # Use core helper enter_registry_test_mode so method_direct_trigger 
        # runs safely under 19.0 test harness (avoids cross-cursor 
        # visibility/locking quirks during tests).
        with self.enter_registry_test_mode():
            cron.method_direct_trigger()
        nb_jobs = self.env["queue.job"].search_count([("name", "=", cron.name)])
        self.assertEqual(nb_jobs, 0)

        # Enable run_as_queue_job and trigger via method_direct_trigger
        cron.write({"run_as_queue_job": True, "channel_id": default_channel.id})
        with self.enter_registry_test_mode():
            cron.method_direct_trigger()
        qjob = self.env["queue.job"].search([("name", "=", cron.name)])
        self.assertTrue(qjob)
        self.assertEqual(qjob.name, cron.name)
        self.assertEqual(qjob.priority, cron.priority)
        self.assertEqual(qjob.user_id, cron.user_id)
        self.assertEqual(qjob.channel, cron.channel_id.complete_name)

    def test_queue_job_cron_depends(self):
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        default_channel = self.env.ref("queue_job_cron.channel_root_ir_cron")
        self.assertFalse(cron.run_as_queue_job)
        # Write + assert in a fresh cursor to avoid ir.cron row lock 
        # serialization under 19.0 when scheduler touches it.
        with self.registry.cursor() as cr:
            env2 = self.env(cr=cr)
            cron2 = env2["ir.cron"].browse(cron.id)
            cron2.write({"run_as_queue_job": True})
            self.assertEqual(cron2.channel_id.id, default_channel.id)

    def test_queue_job_cron_run(self):
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        IrCron = self.env["ir.cron"]
        IrCron._run_job_as_queue_job(server_action=cron.ir_actions_server_id)

    def test_queue_job_no_parallelism(self):
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        default_channel = self.env.ref("queue_job_cron.channel_root_ir_cron")
        # Configure + enqueue in a fresh cursor to avoid serialization 
        # conflicts; call _delay_run_job_as_queue_job twice to exercise 
        # identity-based dedup under no_parallel setting.
        with self.registry.cursor() as cr:
            env2 = self.env(cr=cr)
            cron2 = env2["ir.cron"].browse(cron.id)
            cron2.write(
                {
                    "no_parallel_queue_job_run": True,
                    "run_as_queue_job": True,
                    "channel_id": default_channel.id,
                }
            )
            # Enqueue twice via the queue path; identity prevents duplicates
            cron2._delay_run_job_as_queue_job(server_action=cron2.ir_actions_server_id)
            cron2._delay_run_job_as_queue_job(server_action=cron2.ir_actions_server_id)
            nb_jobs2 = env2["queue.job"].search_count([("name", "=", cron2.name)])
            self.assertEqual(nb_jobs2, 1)
            # Allow parallelism and enqueue once more; count increases
            cron2.write({"no_parallel_queue_job_run": False})
            cron2._delay_run_job_as_queue_job(server_action=cron2.ir_actions_server_id)
            nb_jobs2 = env2["queue.job"].search_count([("name", "=", cron2.name)])
            self.assertEqual(nb_jobs2, 2)
        # Cleanup: enqueues above happen in a committed cursor; remove them to
        # avoid leaking pending jobs into subsequent modules (e.g. jobrunner).
        with self.registry.cursor() as cr:
            env2 = self.env(cr=cr)
            env2["queue.job"].sudo().search([("name", "=", cron.name)]).unlink()

    def test_queue_job_cron_callback(self):
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        # Run _callback in a separate cursor because core _callback 
        # commits/rollbacks; main test cursor forbids it. Assert within the 
        # same cursor for deterministic visibility.
        with self.registry.cursor() as cr:
            env2 = self.env(cr=cr)
            count_before = env2["res.partner"].search_count([])
            partner_model = env2.ref("base.model_res_partner")
            action = env2["ir.actions.server"].create(
                {
                    "name": "Queue job cron callback action create partner",
                    "state": "code",
                    "model_id": partner_model.id,
                    "crud_model_id": partner_model.id,
                    "code": "model.name_create('job Cron partner')",
                }
            )
            env2["ir.cron"].browse(cron.id)._callback("Test queue job cron", action.id)
            partners_after = env2["res.partner"].search_count([])
            self.assertEqual(partners_after, count_before + 1)
        # Phase 2: enable run_as_queue_job and ensure callback enqueues a job
        # (not synchronous); use a separate cursor and assert within it.
        with self.registry.cursor() as cr:
            env2 = self.env(cr=cr)
            env2["ir.cron"].browse(cron.id).write({"run_as_queue_job": True})
            count_before = env2["res.partner"].search_count([])
            jobs_before = env2["queue.job"].search_count([])
            partner_model = env2.ref("base.model_res_partner")
            action = env2["ir.actions.server"].create(
                {
                    "name": "Queue job cron callback action create partner",
                    "state": "code",
                    "model_id": partner_model.id,
                    "crud_model_id": partner_model.id,
                    "code": "model.name_create('job Cron partner')",
                }
            )
            env2["ir.cron"].browse(cron.id)._callback("Test queue job cron", action.id)
            partners_after = env2["res.partner"].search_count([])
            jobs_after = env2["queue.job"].search_count([])
            self.assertEqual(partners_after, count_before)
            self.assertEqual(jobs_after, jobs_before + 1)
        # Cleanup: ensure no leakage across tests when using a shared DB name
        with self.registry.cursor() as cr:
            env2 = self.env(cr=cr)
            cron2 = env2["ir.cron"].browse(cron.id)
            jobs = env2["queue.job"].sudo().search([("name", "=", cron2.name)])
            jobs.unlink()
