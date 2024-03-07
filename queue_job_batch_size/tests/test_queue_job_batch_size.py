# Copyright 2023 Akretion (http://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestQueueJobBatchSize(common.SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.records = (
            cls.env.ref("base.res_partner_1")
            | cls.env.ref("base.res_partner_2")
            | cls.env.ref("base.res_partner_3")
            | cls.env.ref("base.res_partner_4")
            | cls.env.ref("base.res_partner_10")
            | cls.env.ref("base.res_partner_12")
            | cls.env.ref("base.res_partner_18")
        )

    def test_queue_job_batch_size(self):
        self.env["queue.job"].search([]).unlink()
        self.env["queue.job.batch"].search([]).unlink()
        self.records.with_delay(
            description="Test Queue Job Batch Size",
            batch_size=2,
        ).name_get()
        queue_jobs = self.env["queue.job"].search([])
        self.assertEqual(len(queue_jobs), 4)
        self.assertEqual(
            set(queue_jobs.mapped("name")),
            {
                "Test Queue Job Batch Size (batch 1/4)",
                "Test Queue Job Batch Size (batch 2/4)",
                "Test Queue Job Batch Size (batch 3/4)",
                "Test Queue Job Batch Size (batch 4/4)",
            },
        )
        self.assertTrue(
            [len(job.records) for job in queue_jobs],
            [2, 2, 2, 1],
        )
        self.assertTrue(
            all(
                job1.job_batch_id == job2.job_batch_id
                for job1, job2 in zip(queue_jobs, queue_jobs[1:])
            )
        )
        queue_batches = self.env["queue.job.batch"].search([])
        self.assertEqual(len(queue_batches), 1)
        self.assertEqual(
            queue_batches.name,
            "Batch of Test Queue Job Batch Size",
        )

    def test_queue_job_batch_size_other_size_4(self):
        self.env["queue.job"].search([]).unlink()
        self.records.with_delay(
            description="Test Queue Job Batch Size",
            batch_size=4,
        ).name_get()
        queue_jobs = self.env["queue.job"].search([])
        self.assertEqual(len(queue_jobs), 2)
        self.assertTrue(
            [len(job.records) for job in queue_jobs],
            [4, 3],
        )

    def test_queue_job_batch_size_other_size_3(self):
        self.env["queue.job"].search([]).unlink()
        self.records.with_delay(
            description="Test Queue Job Batch Size",
            batch_size=3,
        ).name_get()
        queue_jobs = self.env["queue.job"].search([])
        self.assertEqual(len(queue_jobs), 3)
        self.assertTrue(
            [len(job.records) for job in queue_jobs],
            [3, 3, 1],
        )

    def test_queue_job_batch_size_other_size_1(self):
        self.env["queue.job"].search([]).unlink()
        self.records.with_delay(
            description="Test Queue Job Batch Size",
            batch_size=1,
        ).name_get()
        queue_jobs = self.env["queue.job"].search([])
        self.assertEqual(len(queue_jobs), 7)
        self.assertTrue(
            [len(job.records) for job in queue_jobs],
            [1, 1, 1, 1, 1, 1, 1],
        )

    def test_queue_job_batch_size_other_size_7(self):
        self.env["queue.job"].search([]).unlink()
        self.records.with_delay(
            description="Test Queue Job Batch Size",
            batch_size=7,
        ).name_get()
        queue_jobs = self.env["queue.job"].search([])
        self.assertEqual(len(queue_jobs), 1)
        self.assertTrue(
            [len(job.records) for job in queue_jobs],
            [7],
        )

    def test_queue_job_batch_size_other_size_15(self):
        self.env["queue.job"].search([]).unlink()
        self.records.with_delay(
            description="Test Queue Job Batch Size",
            batch_size=15,
        ).name_get()
        queue_jobs = self.env["queue.job"].search([])
        self.assertEqual(len(queue_jobs), 1)
        self.assertTrue(
            [len(job.records) for job in queue_jobs],
            [7],
        )

    def test_queue_job_batch_size_batch_count(self):
        self.env["queue.job"].search([]).unlink()
        self.records.with_delay(
            description="Test Queue Job Batch Size",
            batch_count=4,
        ).name_get()
        queue_jobs = self.env["queue.job"].search([])
        self.assertEqual(len(queue_jobs), 4)
        self.assertTrue(
            [len(job.records) for job in queue_jobs],
            [2, 2, 2, 1],
        )

    def test_queue_job_batch_size_batch_count_1(self):
        self.env["queue.job"].search([]).unlink()
        self.records.with_delay(
            description="Test Queue Job Batch Size",
            batch_count=1,
        ).name_get()
        queue_jobs = self.env["queue.job"].search([])
        self.assertEqual(len(queue_jobs), 1)
        self.assertTrue(
            [len(job.records) for job in queue_jobs],
            [7],
        )

    def test_queue_job_batch_size_batch_count_7(self):
        self.env["queue.job"].search([]).unlink()
        self.records.with_delay(
            description="Test Queue Job Batch Size",
            batch_count=7,
        ).name_get()
        queue_jobs = self.env["queue.job"].search([])
        self.assertEqual(len(queue_jobs), 7)
        self.assertTrue(
            [len(job.records) for job in queue_jobs],
            [1, 1, 1, 1, 1, 1, 1],
        )

    def test_queue_job_batch_size_batch_count_15(self):
        self.env["queue.job"].search([]).unlink()
        self.records.with_delay(
            description="Test Queue Job Batch Size",
            batch_count=15,
        ).name_get()
        queue_jobs = self.env["queue.job"].search([])
        self.assertEqual(len(queue_jobs), 7)
        self.assertTrue(
            [len(job.records) for job in queue_jobs],
            [1, 1, 1, 1, 1, 1, 1],
        )

    def test_queue_job_batch_size_no_description(self):
        self.env["queue.job"].search([]).unlink()
        self.env["queue.job.batch"].search([]).unlink()
        self.records.with_delay(
            batch_size=2,
        ).name_get()
        queue_jobs = self.env["queue.job"].search([])
        self.assertEqual(len(queue_jobs), 4)
        self.assertEqual(
            set(queue_jobs.mapped("name")),
            {
                "res.partner.name_get (batch 1/4)",
                "res.partner.name_get (batch 2/4)",
                "res.partner.name_get (batch 3/4)",
                "res.partner.name_get (batch 4/4)",
            },
        )

        queue_batches = self.env["queue.job.batch"].search([])
        self.assertEqual(len(queue_batches), 1)
        self.assertEqual(
            queue_batches.name,
            "Batch of res.partner.name_get",
        )
