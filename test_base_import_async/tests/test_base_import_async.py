# -*- coding: utf-8 -*-
###############################################################################
#
#   Module for OpenERP
#   Copyright (C) 2014 ACSONE SA/NV (http://acsone.eu).
#   @author Stéphane Bidoul <stephane.bidoul@acsone.eu>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import os

import openerp.tests.common as common
from openerp.addons.base_import_async.models.base_import_async import (
    OPT_HAS_HEADER, OPT_QUOTING, OPT_SEPARATOR,
    OPT_CHUNK_SIZE, OPT_USE_CONNECTOR
)
from openerp.addons.connector.queue.job import OpenERPJobStorage
from openerp.addons.connector.session import ConnectorSession


class TestBaseImportConnector(common.TransactionCase):

    FIELDS = [
        'date',
        'journal_id/id',
        'name',
        'period_id/id',
        'ref',
        'line_id/account_id/id',
        'line_id/name',
        'line_id/debit',
        'line_id/credit',
        'line_id/partner_id/id',
    ]
    OPTIONS = {
        OPT_SEPARATOR: ',',
        OPT_QUOTING: '"',
        OPT_HAS_HEADER: True,
    }

    def setUp(self):
        super(TestBaseImportConnector, self).setUp()
        self.import_obj = self.registry['base_import.import']
        self.move_obj = self.registry['account.move']
        self.job_obj = self.registry['queue.job']
        self.session = ConnectorSession(self.cr, self.uid)
        self.storage = OpenERPJobStorage(self.session)

    def _read_test_file(self, file_name):
        file_name = os.path.join(os.path.dirname(__file__), file_name)
        return open(file_name).read()

    def _do_import(self, file_name, use_connector, chunk_size=None):
        data = self._read_test_file(file_name)
        import_id = self.import_obj.create(self.cr, self.uid, {
            'res_model': 'account.move',
            'file': data,
            'file_name': file_name,
        })
        options = dict(self.OPTIONS)
        options[OPT_USE_CONNECTOR] = use_connector
        options[OPT_CHUNK_SIZE] = chunk_size
        return self.import_obj.do(
            self.cr, self.uid, import_id, self.FIELDS, options)

    def _check_import_result(self):
        move_ids = self.move_obj.search(
            self.cr, self.uid,
            [('name', 'in', ('TEST-1', 'TEST-2', 'TEST-3'))])
        self.assertEqual(len(move_ids), 3)

    def test_normal_import(self):
        """ Test the standard import still works. """
        res = self._do_import('account.move.csv', use_connector=False)
        self.assertFalse(res, repr(res))
        self._check_import_result()

    def test_async_import(self):
        """ Basic asynchronous import test with default large chunk size. """
        res = self._do_import('account.move.csv', use_connector=True)
        self.assertFalse(res, repr(res))
        # no moves should be created yet
        move_ids = self.move_obj.search(
            self.cr, self.uid,
            [('name', 'in', ('TEST-1', 'TEST-2', 'TEST-3'))])
        self.assertEqual(len(move_ids), 0)
        # but we must have one job to split the file
        split_job_ids = self.job_obj.search(self.cr, self.uid, [])
        self.assertEqual(len(split_job_ids), 1)
        split_job = self.job_obj.browse(self.cr, self.uid, split_job_ids[0])
        # job names are important
        self.assertEqual(split_job.name,
                         "Import Account Entry from file account.move.csv")
        # perform job
        self.storage.load(split_job.uuid).perform(self.session)
        # check one job has been generated to load the file (one chunk)
        load_job_ids = self.job_obj.search(self.cr, self.uid,
                                           [('id', '!=', split_job.id)])
        self.assertEqual(len(load_job_ids), 1)
        load_job = self.job_obj.browse(self.cr, self.uid, load_job_ids[0])
        self.assertEqual(load_job.name,
                         "Import Account Entry from file account.move.csv - "
                         "#0 - lines 2 to 10")
        # perform job
        self.storage.load(load_job.uuid).perform(self.session)
        self._check_import_result()

    def test_async_import_small_misaligned_chunks(self):
        """ Chunk size larger than record. """
        res = self._do_import('account.move.csv', use_connector=True,
                              chunk_size=4)
        self.assertFalse(res, repr(res))
        # but we must have one job to split the file
        split_job_ids = self.job_obj.search(self.cr, self.uid, [])
        self.assertEqual(len(split_job_ids), 1)
        split_job = self.job_obj.browse(self.cr, self.uid, split_job_ids[0])
        # perform job
        self.storage.load(split_job.uuid).perform(self.session)
        # check one job has been generated to load the file (two chunks)
        load_job_ids = self.job_obj.search(self.cr, self.uid,
                                           [('id', '!=', split_job.id)],
                                           order='name')
        self.assertEqual(len(load_job_ids), 2)
        load_jobs = self.job_obj.browse(self.cr, self.uid, load_job_ids)
        self.assertEqual(load_jobs[0].name,
                         "Import Account Entry from file account.move.csv - "
                         "#0 - lines 2 to 7")
        self.assertEqual(load_jobs[1].name,
                         "Import Account Entry from file account.move.csv - "
                         "#1 - lines 8 to 10")
        # perform job
        self.storage.load(load_jobs[0].uuid).perform(self.session)
        self.storage.load(load_jobs[1].uuid).perform(self.session)
        self._check_import_result()

    def test_async_import_smaller_misaligned_chunks(self):
        """ Chunk size smaller than record. """
        res = self._do_import('account.move.csv', use_connector=True,
                              chunk_size=2)
        self.assertFalse(res, repr(res))
        # but we must have one job to split the file
        split_job_ids = self.job_obj.search(self.cr, self.uid, [])
        self.assertEqual(len(split_job_ids), 1)
        split_job = self.job_obj.browse(self.cr, self.uid, split_job_ids[0])
        # perform job
        self.storage.load(split_job.uuid).perform(self.session)
        # check one job has been generated to load the file (three chunks)
        load_job_ids = self.job_obj.search(self.cr, self.uid,
                                           [('id', '!=', split_job.id)],
                                           order='name')
        self.assertEqual(len(load_job_ids), 3)
        load_jobs = self.job_obj.browse(self.cr, self.uid, load_job_ids)
        self.assertEqual(load_jobs[0].name,
                         "Import Account Entry from file account.move.csv - "
                         "#0 - lines 2 to 4")
        self.assertEqual(load_jobs[1].name,
                         "Import Account Entry from file account.move.csv - "
                         "#1 - lines 5 to 7")
        self.assertEqual(load_jobs[2].name,
                         "Import Account Entry from file account.move.csv - "
                         "#2 - lines 8 to 10")
        # perform job
        self.storage.load(load_jobs[0].uuid).perform(self.session)
        self.storage.load(load_jobs[1].uuid).perform(self.session)
        self.storage.load(load_jobs[2].uuid).perform(self.session)
        self._check_import_result()

    def test_async_import_smaller_aligned_chunks(self):
        """ Chunks aligned on record boundaries.
        Last chunk ends exactly at file end. """
        res = self._do_import('account.move.csv', use_connector=True,
                              chunk_size=3)
        self.assertFalse(res, repr(res))
        # but we must have one job to split the file
        split_job_ids = self.job_obj.search(self.cr, self.uid, [])
        self.assertEqual(len(split_job_ids), 1)
        split_job = self.job_obj.browse(self.cr, self.uid, split_job_ids[0])
        # perform job
        self.storage.load(split_job.uuid).perform(self.session)
        # check one job has been generated to load the file (three chunks)
        load_job_ids = self.job_obj.search(self.cr, self.uid,
                                           [('id', '!=', split_job.id)],
                                           order='name')
        self.assertEqual(len(load_job_ids), 3)
        load_jobs = self.job_obj.browse(self.cr, self.uid, load_job_ids)
        self.assertEqual(load_jobs[0].name,
                         "Import Account Entry from file account.move.csv - "
                         "#0 - lines 2 to 4")
        self.assertEqual(load_jobs[1].name,
                         "Import Account Entry from file account.move.csv - "
                         "#1 - lines 5 to 7")
        self.assertEqual(load_jobs[2].name,
                         "Import Account Entry from file account.move.csv - "
                         "#2 - lines 8 to 10")
        # perform job
        self.storage.load(load_jobs[0].uuid).perform(self.session)
        self.storage.load(load_jobs[1].uuid).perform(self.session)
        self.storage.load(load_jobs[2].uuid).perform(self.session)
        self._check_import_result()
