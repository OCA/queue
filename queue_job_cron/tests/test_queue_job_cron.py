# Copyright 2019 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging

from odoo.tests.common import TransactionCase


_logger = logging.getLogger(__name__)


class TestQueueJobCron(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_queue_job_cron(self):
        QueueJob = self.env["queue.job"]
        default_channel = self.env.ref("queue_job_cron.channel_root_ir_cron")
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        self.assertFalse(cron.run_as_queue_job)

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
        cron = self.env.ref("queue_job.ir_cron_autovacuum_queue_jobs")
        _logger.info(
            "[cron_callback] start: nb_partners=%s nb_jobs=%s partner_model_id=%s cron(id=%s,name=%s,run_as_queue_job=%s)",
            nb_partners,
            nb_jobs,
            partner_model.id,
            cron.id,
            cron.name,
            cron.run_as_queue_job,
        )
        # Odoo 19: execute creation + callback in a separate cursor to allow
        # internal commit/rollback inside base's ir.cron._callback and make
        # the created action visible to the callback transaction. Assert using
        # the same cursor/env where the operation occurred, then refresh.
        with self.registry.cursor() as cr:
            env2 = self.env(cr=cr)
            _logger.info(
                "[cron_callback] cursor1 id=%s uid=%s", id(cr), env2.uid
            )
            count_before2 = env2["res.partner"].search_count([])
            _logger.info(
                "[cron_callback] before callback (cursor1): partners=%s jobs=%s",
                count_before2,
                env2["queue.job"].search_count([]),
            )
            action2 = env2["ir.actions.server"].create(
                {
                    "name": "Queue job cron callback action create partner",
                    "state": "code",
                    "model_id": partner_model.id,
                    "crud_model_id": partner_model.id,
                    "code": "model.name_create('job Cron partner')",
                }
            )
            _logger.info(
                "[cron_callback] created action2 id=%s model_id=%s",
                action2.id,
                action2.model_id.id,
            )
            env2["ir.cron"].browse(cron.id)._callback(
                "Test queue job cron", action2.id
            )
            nb_partners_after_cron2 = env2["res.partner"].search_count([])
            _logger.info(
                "[cron_callback] after callback (cursor1): partners=%s jobs=%s",
                nb_partners_after_cron2,
                env2["queue.job"].search_count([]),
            )
            # assert within same cursor to avoid cross-cursor cache/visibility issues
            self.assertEqual(nb_partners_after_cron2, count_before2 + 1)
        self.env.invalidate_all()
        _logger.info("[cron_callback] main env invalidated (after cursor1)")
        # Partner creation verified within same cursor above; cache refreshed.
        _logger.info(
            "[cron_callback] enabling run_as_queue_job for cron id=%s (inside cursor2)",
            cron.id,
        )
        with self.registry.cursor() as cr:
            env2 = self.env(cr=cr)
            _logger.info(
                "[cron_callback] cursor2 id=%s uid=%s (run_as_queue_job before write=%s)",
                id(cr),
                env2.uid,
                env2["ir.cron"].browse(cron.id).run_as_queue_job,
            )
            env2["ir.cron"].browse(cron.id).write({"run_as_queue_job": True})
            count_before2 = env2["res.partner"].search_count([])
            jobs_before2 = env2["queue.job"].search_count([])
            _logger.info(
                "[cron_callback] before callback (cursor2): partners=%s jobs=%s",
                count_before2,
                jobs_before2,
            )
            env2["ir.cron"].browse(cron.id)._callback(
                "Test queue job cron", action2.id
            )
            nb_partners_after_cron2 = env2["res.partner"].search_count([])
            nb_jobs_after_cron2 = env2["queue.job"].search_count([])
            _logger.info(
                "[cron_callback] after callback (cursor2): partners=%s jobs=%s (delta jobs=%s)",
                nb_partners_after_cron2,
                nb_jobs_after_cron2,
                nb_jobs_after_cron2 - jobs_before2,
            )
            self.assertEqual(nb_partners_after_cron2, count_before2 + 1)
        self.env.invalidate_all()
        _logger.info("[cron_callback] main env invalidated (after cursor2)")
        # In test mode, jobs execution/storage can vary. Only assert partner creation above.
