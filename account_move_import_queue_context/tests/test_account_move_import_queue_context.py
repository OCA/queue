from odoo.tests.common import TransactionCase


class TestJobPrepareContext(TransactionCase):
    def test_job_prepare_context_before_enqueue_keys(self):
        # Calls the method _job_prepare_context_before_enqueue_keys
        context_keys = self.env["base"]._job_prepare_context_before_enqueue_keys()

        # Checks if the key is in the context
        self.assertIn("default_move_type", context_keys)
