# Copyright 2014 ACSONE SA/NV (http://acsone.eu)
# @author Stéphane Bidoul <stephane.bidoul@acsone.eu>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import os

import odoo.tests.common as common

from odoo.addons.base_import_async.models.base_import_import import (
    OPT_CHUNK_SIZE,
    OPT_HAS_HEADER,
    OPT_QUOTING,
    OPT_SEPARATOR,
    OPT_USE_QUEUE,
)
from odoo.addons.queue_job.job import Job


class TestBaseImportAsync(common.TransactionCase):

    FIELDS = [
        "date",
        "journal_id/id",
        "name",
        "ref",
        "line_ids/account_id/id",
        "line_ids/name",
        "line_ids/debit",
        "line_ids/credit",
        "line_ids/partner_id/id",
    ]
    OPTIONS = {
        OPT_SEPARATOR: ",",
        OPT_QUOTING: '"',
        OPT_HAS_HEADER: True,
        "date_format": "%Y-%m-%d",
    }

    def setUp(self):
        super().setUp()
        # add xmlids that will be used in the test CSV file
        self.env["ir.model.data"]._update_xmlids(
            [
                {
                    "xml_id": "test_base_import_async.testjournal_xmlid",
                    "record": self.env["account.journal"].search(
                        [("code", "=", "CABA")]
                    ),
                },
                {
                    "xml_id": "test_base_import_async.a_recv_xmlid",
                    "record": self.env["account.account"].search(
                        [("code", "=", "121000")]
                    ),
                },
                {
                    "xml_id": "test_base_import_async.a_sale_xmlid",
                    "record": self.env["account.account"].search(
                        [("code", "=", "400000")]
                    ),
                },
            ]
        )
        self.import_obj = self.env["base_import.import"]
        self.move_obj = self.env["account.move"]
        self.job_obj = self.env["queue.job"]

    def _read_test_file(self, file_name):
        file_name = os.path.join(os.path.dirname(__file__), file_name)
        return open(file_name).read()

    def _do_import(self, file_name, use_queue, chunk_size=None):
        data = self._read_test_file(file_name)
        importer = self.import_obj.create(
            {"res_model": "account.move", "file": data, "file_name": file_name}
        )
        options = dict(self.OPTIONS)
        options[OPT_USE_QUEUE] = use_queue
        options[OPT_CHUNK_SIZE] = chunk_size
        return importer.do(self.FIELDS, self.FIELDS, options)

    def _check_import_result(self):
        move_count = self.move_obj.search_count(
            [("name", "in", ("TEST-1", "TEST-2", "TEST-3"))]
        )
        self.assertEqual(move_count, 3)

    def test_normal_import(self):
        """ Test the standard import still works. """
        res = self._do_import("account.move.csv", use_queue=False)
        self.assertFalse(res["messages"], repr(res))
        self._check_import_result()

    def test_async_import(self):
        """ Basic asynchronous import test with default large chunk size. """
        res = self._do_import("account.move.csv", use_queue=True)
        self.assertFalse(res, repr(res))
        # no moves should be created yet
        move_count = self.move_obj.search(
            [("name", "in", ("TEST-1", "TEST-2", "TEST-3"))]
        )
        self.assertEqual(len(move_count), 0)
        # but we must have one job to split the file
        split_job = self.job_obj.search([])
        self.assertEqual(len(split_job), 1)
        # job names are important
        self.assertEqual(
            split_job.name, "Import Journal Entries from file account.move.csv"
        )
        # perform job
        Job.load(self.env, split_job.uuid).perform()
        # check one job has been generated to load the file (one chunk)
        load_job = self.job_obj.search([("id", "!=", split_job.id)])
        self.assertEqual(len(load_job), 1)
        self.assertEqual(
            load_job.name,
            "Import Journal Entries from file account.move.csv - " "#0 - lines 2 to 10",
        )
        # perform job
        Job.load(self.env, load_job.uuid).perform()
        self._check_import_result()

    def test_async_import_small_misaligned_chunks(self):
        """ Chunk size larger than record. """
        res = self._do_import("account.move.csv", use_queue=True, chunk_size=4)
        self.assertFalse(res, repr(res))
        # but we must have one job to split the file
        split_job = self.job_obj.search([])
        self.assertEqual(len(split_job), 1)
        # perform job
        Job.load(self.env, split_job.uuid).perform()
        # check one job has been generated to load the file (two chunks)
        load_jobs = self.job_obj.search([("id", "!=", split_job.id)], order="name")
        self.assertEqual(len(load_jobs), 2)
        self.assertEqual(
            load_jobs[0].name,
            "Import Journal Entries from file account.move.csv - " "#0 - lines 2 to 7",
        )
        self.assertEqual(
            load_jobs[1].name,
            "Import Journal Entries from file account.move.csv - " "#1 - lines 8 to 10",
        )
        # perform job
        Job.load(self.env, load_jobs[0].uuid).perform()
        Job.load(self.env, load_jobs[1].uuid).perform()
        self._check_import_result()

    def test_async_import_smaller_misaligned_chunks(self):
        """ Chunk size smaller than record. """
        res = self._do_import("account.move.csv", use_queue=True, chunk_size=2)
        self.assertFalse(res, repr(res))
        # but we must have one job to split the file
        split_job = self.job_obj.search([])
        self.assertEqual(len(split_job), 1)
        # perform job
        Job.load(self.env, split_job.uuid).perform()
        # check one job has been generated to load the file (three chunks)
        load_jobs = self.job_obj.search([("id", "!=", split_job.id)], order="name")
        self.assertEqual(len(load_jobs), 3)
        self.assertEqual(
            load_jobs[0].name,
            "Import Journal Entries from file account.move.csv - " "#0 - lines 2 to 4",
        )
        self.assertEqual(
            load_jobs[1].name,
            "Import Journal Entries from file account.move.csv - " "#1 - lines 5 to 7",
        )
        self.assertEqual(
            load_jobs[2].name,
            "Import Journal Entries from file account.move.csv - " "#2 - lines 8 to 10",
        )
        # perform job
        Job.load(self.env, load_jobs[0].uuid).perform()
        Job.load(self.env, load_jobs[1].uuid).perform()
        Job.load(self.env, load_jobs[2].uuid).perform()
        self._check_import_result()

    def test_async_import_smaller_aligned_chunks(self):
        """ Chunks aligned on record boundaries.
        Last chunk ends exactly at file end. """
        res = self._do_import("account.move.csv", use_queue=True, chunk_size=3)
        self.assertFalse(res, repr(res))
        # but we must have one job to split the file
        split_job = self.job_obj.search([])
        self.assertEqual(len(split_job), 1)
        # perform job
        Job.load(self.env, split_job.uuid).perform()
        # check one job has been generated to load the file (three chunks)
        load_jobs = self.job_obj.search([("id", "!=", split_job.id)], order="name")
        self.assertEqual(len(load_jobs), 3)
        self.assertEqual(
            load_jobs[0].name,
            "Import Journal Entries from file account.move.csv - " "#0 - lines 2 to 4",
        )
        self.assertEqual(
            load_jobs[1].name,
            "Import Journal Entries from file account.move.csv - " "#1 - lines 5 to 7",
        )
        self.assertEqual(
            load_jobs[2].name,
            "Import Journal Entries from file account.move.csv - " "#2 - lines 8 to 10",
        )
        # perform job
        Job.load(self.env, load_jobs[0].uuid).perform()
        Job.load(self.env, load_jobs[1].uuid).perform()
        Job.load(self.env, load_jobs[2].uuid).perform()
        self._check_import_result()
