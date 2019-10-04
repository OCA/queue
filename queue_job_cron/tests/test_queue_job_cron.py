# Copyright 2019 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo.tests.common import TransactionCase


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
        self.assertEqual(qjob.channel, cron.channel_id.name)

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
