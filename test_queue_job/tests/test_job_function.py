import odoo.tests.common as common
from odoo import exceptions


class TestJobFunction(common.TransactionCase):
    def setUp(self):
        super(TestJobFunction, self).setUp()
        self.test_function_model = self.env.ref(
            "queue_job.job_function_queue_job__test_job"
        )

    def test_check_retry_pattern_randomized_case(self):
        randomized_pattern = "{1: (10, 20), 2: (20, 40)}"
        self.test_function_model.edit_retry_pattern = randomized_pattern
        self.assertEqual(
            self.test_function_model.edit_retry_pattern, randomized_pattern
        )

    def test_check_retry_pattern_fixed_case(self):
        fixed_pattern = "{1: 10, 2: 20}"
        self.test_function_model.edit_retry_pattern = fixed_pattern
        self.assertEqual(self.test_function_model.edit_retry_pattern, fixed_pattern)

    def test_check_retry_pattern_invalid_cases(self):
        invalid_time_value_pattern = "{1: a, 2: 20}"
        with self.assertRaises(exceptions.UserError):
            self.test_function_model.edit_retry_pattern = invalid_time_value_pattern

        invalid_retry_count_pattern = "{a: 10, 2: 20}"
        with self.assertRaises(exceptions.UserError):
            self.test_function_model.edit_retry_pattern = invalid_retry_count_pattern

        invalid_randomized_pattern = "{1: (1, 2, 3), 2: 20}"
        with self.assertRaises(exceptions.UserError):
            self.test_function_model.edit_retry_pattern = invalid_randomized_pattern
