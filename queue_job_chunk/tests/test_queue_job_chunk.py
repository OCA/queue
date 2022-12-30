#  Copyright (c) Akretion 2020
#  License AGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)


from odoo_test_helper import FakeModelLoader

from odoo.tests import TransactionCase


class TestQueueJobChunk(TransactionCase, FakeModelLoader):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.loader = FakeModelLoader(cls.env, cls.__module__)
        cls.loader.backup_registry()
        from .models import QueueJobChunk, TestOdooStateProcessor

        cls.loader.update_registry((TestOdooStateProcessor, QueueJobChunk))

        cls.env = cls.env(context=dict(cls.env.context, test_queue_job_no_delay=True))
        cls.main_company = cls.env.ref("base.main_company")
        cls.another_company_partner = cls.env["res.partner"].create(
            {"name": "Company2"}
        )
        cls.another_company = cls.env["res.company"].create(
            {
                "name": cls.another_company_partner.name,
                "partner_id": cls.another_company_partner.id,
                "currency_id": cls.env.ref("base.main_company").currency_id.id,
            }
        )
        cls.partner = cls.env.ref("base.res_partner_3")
        cls.chunk_data_contact = [
            {
                "data_str": '{"name": "Steve Queue Job"}',
                "processor": "test_partner",
                "model_name": "res.partner",
                "record_id": cls.partner.id,
            },
            {
                "data_str": '{"name": "Other"}',
                "processor": "test_partner",
                "model_name": "res.partner",
                "record_id": cls.partner.id,
            },
        ]
        cls.chunk_data_bad = {
            "data_str": "{''(;,),x*}",
            "processor": "test_partner",
            "model_name": "res.partner",
            "record_id": cls.partner.id,
        }
        USA = cls.env.ref("base.us")
        cls.chunk_data_state = {
            "processor": "test_state",
            "data_str": '{"name": "New Stateshire", "code": "NS", "country_id": %d}'
            % USA.id,
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
