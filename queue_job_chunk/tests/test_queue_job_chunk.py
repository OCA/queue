#  Copyright (c) Akretion 2020
#  License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)


from odoo.addons.component.tests.common import TransactionComponentCase


class TestQueueJobChunk(TransactionComponentCase):
    def setUp(self):
        super().setUp()
        self.env = self.env(
            context=dict(self.env.context, test_queue_job_no_delay=True)
        )

    def test_create_chunk(self):
        partner_count = self.env["res.partner"].search_count([])
        module_count = self.env["ir.module.module"].search_count([])

        chunk_data_1 = "{'name': 'Steve Queue Job'}"
        chunk_vals_1 = {
            "apply_on_model": "res.partner",
            "data_str": chunk_data_1,
            "usage": "basic_create",
        }

        chunk_data_2 = "{'name': 'New Module Name'}"
        chunk_vals_2 = {
            "apply_on_model": "ir.module.module",
            "data_str": chunk_data_2,
            "usage": "basic_create",
        }
        chunk_vals = [chunk_vals_1, chunk_vals_2]
        self.env["queue.job.chunk"].create(chunk_vals)
        new_partner_count = self.env["res.partner"].search_count([])
        new_module_count = self.env["ir.module.module"].search_count([])
        self.assertEqual(partner_count + 1, new_partner_count)
        self.assertEqual(module_count + 1, new_module_count)

    def test_create_chunk_fail_retry(self):
        partner_count = self.env["res.partner"].search_count([])
        chunk_data = "{':::'Bad json format}"
        chunk_vals = {
            "apply_on_model": "res.partner",
            "data_str": chunk_data,
            "usage": "basic_create",
        }

        chunk = self.env["queue.job.chunk"].create(chunk_vals)
        new_partner_count = self.env["res.partner"].search_count([])
        self.assertEqual(partner_count, new_partner_count)
        self.assertEqual(chunk.state, "fail")
        # retry with correct data
        chunk.data_str = "{'name': 'Steve Queue Job'}"
        chunk.button_retry()
        new_partner_count = self.env["res.partner"].search_count([])
        self.assertEqual(partner_count + 1, new_partner_count)
