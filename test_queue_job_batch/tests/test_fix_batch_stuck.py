from odoo.tests.common import TransactionCase


class TestQueueJobBatchFix(TransactionCase):
    def setUp(self):
        super().setUp()
        self.QueueJob = self.env["queue.job"]
        self.Batch = self.env["queue.job.batch"]
        self.TestModel = self.env["test.queue.job"]

    def test_batch_failed_job_triggers_check(self):
        """Test that a failed job triggers check_state on the batch."""
        self.cr.execute("delete from queue_job")
        batch = self.Batch.get_new_batch("TEST_FAIL")

        # Create a job in the batch
        job = self.TestModel.with_context(job_batch=batch).with_delay().testing_method()
        job_record = job.db_record()

        # Verify initial state
        self.assertEqual(batch.state, "pending")
        self.assertEqual(job_record.state, "pending")

        # Set job to failed
        # Depending on how queue_job works, writing state might trigger the logic
        job_record.write({"state": "failed", "exc_info": "Fail"})

        # Find jobs for queue.job.batch
        check_jobs = self.QueueJob.search(
            [
                ("model_name", "=", "queue.job.batch"),
                ("method_name", "=", "check_state"),
            ]
        )

        # Filter for our batch
        check_jobs = check_jobs.filtered(lambda j: batch in j.records)

        # WITHOUT FIX: This should be empty because "failed" state doesn't trigger
        self.assertTrue(
            check_jobs, "check_state job should be created when a job fails"
        )

    def test_batch_cancelled_job_triggers_check(self):
        """Test that a cancelled job triggers check_state on the batch."""
        self.cr.execute("delete from queue_job")
        batch = self.Batch.get_new_batch("TEST_CANCEL")
        job = self.TestModel.with_context(job_batch=batch).with_delay().testing_method()
        job_record = job.db_record()

        job_record.write({"state": "cancelled"})

        check_jobs = self.QueueJob.search(
            [
                ("model_name", "=", "queue.job.batch"),
                ("method_name", "=", "check_state"),
            ]
        )
        check_jobs = check_jobs.filtered(lambda j: batch in j.records)

        self.assertTrue(
            check_jobs, "check_state job should be created when a job is cancelled"
        )

    def test_no_deduplication_race_condition(self):
        """Test that multiple jobs trigger multiple check_state calls."""
        self.cr.execute("delete from queue_job")
        batch = self.Batch.get_new_batch("TEST_RACE")

        # Create 2 jobs
        job1 = (
            self.TestModel.with_context(job_batch=batch).with_delay().testing_method()
        )
        job2 = (
            self.TestModel.with_context(job_batch=batch).with_delay().testing_method()
        )

        # Set job1 to done -> creates CheckJob1
        job1.db_record().write({"state": "done"})

        # Set job2 to done -> creates CheckJob2
        # If identity_exact is used, CheckJob2 might be deduplicated
        job2.db_record().write({"state": "done"})

        check_jobs = self.QueueJob.search(
            [
                ("model_name", "=", "queue.job.batch"),
                ("method_name", "=", "check_state"),
            ]
        )
        check_jobs = check_jobs.filtered(lambda j: batch in j.records)

        # WITH FIX: Should have 2 check jobs (no deduplication)
        # WITHOUT FIX: Should have 1 check job because of deduplication
        self.assertEqual(
            len(check_jobs), 2, "Should have 2 check_state jobs (no deduplication)"
        )
