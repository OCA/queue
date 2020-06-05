#  Copyright (c) Akretion 2020
#  License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)


from odoo.addons.component.tests.common import TransactionComponentCase


class TestQueueJobChunk(TransactionComponentCase):
    def setUp(self):
        super().setUp()
        self.env = self.env(
            context=dict(self.env.context, test_queue_job_no_delay=True)
        )
        self.main_company = self.env.ref("base.main_company")
        self.another_company_partner = self.env["res.partner"].create(
            {"name": "Company2"}
        )
        self.another_company = self.env["res.company"].create(
            {
                "name": self.another_company_partner.name,
                "partner_id": self.another_company_partner.id,
                "currency_id": self.env.ref("base.main_company").currency_id.id,
            }
        )
        self.partner = self.env.ref("base.res_partner_3")
        self.chunk_data_contact = [
            {
                "apply_on_model": "res.partner",
                "data_str": '{"name": "Steve Queue Job"}',
                "usage": "basic_create",
                "model_name": "res.partner",
                "record_id": self.partner.id,
            },
            {
                "apply_on_model": "res.partner",
                "data_str": '{"name": "Other"}',
                "usage": "basic_create",
                "model_name": "res.partner",
                "record_id": self.partner.id,
            },
        ]
        self.chunk_data_bad = {
            "apply_on_model": "res.partner",
            "data_str": "{''(;,),x*}",
            "usage": "basic_create",
            "model_name": "res.partner",
            "record_id": self.partner.id,
        }
        USA = self.env.ref("base.us")
        self.chunk_data_state = {
            "apply_on_model": "res.country.state",
            "data_str": '{"name": "New Stateshire", "code": "NS", "country_id": %d}'
            % USA.id,
            "usage": "basic_create",
            "model_name": "res.country",
            "record_id": USA.id,
        }

    def test_create_chunk(self):
        partner_count = self.env["res.partner"].search_count([])
        chunk = self.env["queue.job.chunk"].create(self.chunk_data_contact)
        new_partner_count = self.env["res.partner"].search_count([])
        self.assertEqual(chunk[0].state, "done")
        self.assertEqual(chunk[1].state, "done")
        self.assertEqual(partner_count + 2, new_partner_count)

    def test_create_chunk_fail_retry(self):
        partner_count = self.env["res.partner"].search_count([])
        # fail with bad data
        chunk = self.env["queue.job.chunk"].create(self.chunk_data_bad)
        self.assertEqual(chunk.state, "fail")

        # retry with correct data
        chunk.data_str = '{"name": "Steve Queue Job"}'
        chunk.button_retry()
        new_partner_count = self.env["res.partner"].search_count([])
        self.assertEqual(partner_count + 1, new_partner_count)

    def test_create_chunk_without_company_id(self):
        chunk = self.env["queue.job.chunk"].create(self.chunk_data_state)
        self.assertEqual(chunk.company_id, self.env.user.company_id)

    def test_create_chunk_with_company_id(self):
        company = self.partner.company_id
        chunk = self.env["queue.job.chunk"].create(self.chunk_data_contact[0])
        self.assertEqual(company, chunk.company_id)

    def test_reference(self):
        chunk = self.env["queue.job.chunk"].create(self.chunk_data_contact[0])
        self.assertEqual(chunk.reference, self.partner)

    def test_create_chunk_job(self):
        job_count = self.env["queue.job"].search_count([])
        self.env = self.env(
            context=dict(self.env.context, test_queue_job_no_delay=False)
        )
        self.env["queue.job.chunk"].create(self.chunk_data_contact[0])
        new_job_count = self.env["queue.job"].search_count([])
        self.assertEqual(job_count + 1, new_job_count)
