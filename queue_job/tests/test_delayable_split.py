# Copyright 2024 Akretion (http://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import common

# pylint: disable=odoo-addons-relative-import
from odoo.addons.queue_job.delay import Delayable


class TestDelayableSplit(common.BaseCase):
    def setUp(self):
        super().setUp()

        class FakeRecordSet(list):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._name = "recordset"

            def __getitem__(self, key):
                if isinstance(key, slice):
                    return FakeRecordSet(super().__getitem__(key))
                return super().__getitem__(key)

            def method(self, arg, kwarg=None):
                """Method to be called"""
                return arg, kwarg

        self.FakeRecordSet = FakeRecordSet

    def test_delayable_split_no_method_call_beforehand(self):
        dl = Delayable(self.FakeRecordSet(range(20)))
        with self.assertRaises(ValueError):
            dl.split(3)

    def test_delayable_split_10_3(self):
        dl = Delayable(self.FakeRecordSet(range(10)))
        dl.method("arg", kwarg="kwarg")
        group = dl.split(3)
        self.assertEqual(len(group._delayables), 4)
        delayables = sorted(list(group._delayables), key=lambda x: x.description)
        self.assertEqual(delayables[0].recordset, self.FakeRecordSet([0, 1, 2]))
        self.assertEqual(delayables[1].recordset, self.FakeRecordSet([3, 4, 5]))
        self.assertEqual(delayables[2].recordset, self.FakeRecordSet([6, 7, 8]))
        self.assertEqual(delayables[3].recordset, self.FakeRecordSet([9]))
        self.assertEqual(delayables[0].description, "Method to be called (split 1/4)")
        self.assertEqual(delayables[1].description, "Method to be called (split 2/4)")
        self.assertEqual(delayables[2].description, "Method to be called (split 3/4)")
        self.assertEqual(delayables[3].description, "Method to be called (split 4/4)")
        self.assertNotEqual(delayables[0]._job_method, dl._job_method)
        self.assertNotEqual(delayables[1]._job_method, dl._job_method)
        self.assertNotEqual(delayables[2]._job_method, dl._job_method)
        self.assertNotEqual(delayables[3]._job_method, dl._job_method)
        self.assertEqual(delayables[0]._job_method.__name__, dl._job_method.__name__)
        self.assertEqual(delayables[1]._job_method.__name__, dl._job_method.__name__)
        self.assertEqual(delayables[2]._job_method.__name__, dl._job_method.__name__)
        self.assertEqual(delayables[3]._job_method.__name__, dl._job_method.__name__)
        self.assertEqual(delayables[0]._job_args, ("arg",))
        self.assertEqual(delayables[1]._job_args, ("arg",))
        self.assertEqual(delayables[2]._job_args, ("arg",))
        self.assertEqual(delayables[3]._job_args, ("arg",))
        self.assertEqual(delayables[0]._job_kwargs, {"kwarg": "kwarg"})
        self.assertEqual(delayables[1]._job_kwargs, {"kwarg": "kwarg"})
        self.assertEqual(delayables[2]._job_kwargs, {"kwarg": "kwarg"})
        self.assertEqual(delayables[3]._job_kwargs, {"kwarg": "kwarg"})

    def test_delayable_split_10_5(self):
        dl = Delayable(self.FakeRecordSet(range(10)))
        dl.method("arg", kwarg="kwarg")
        group = dl.split(5)
        self.assertEqual(len(group._delayables), 2)
        delayables = sorted(list(group._delayables), key=lambda x: x.description)
        self.assertEqual(delayables[0].recordset, self.FakeRecordSet([0, 1, 2, 3, 4]))
        self.assertEqual(delayables[1].recordset, self.FakeRecordSet([5, 6, 7, 8, 9]))
        self.assertEqual(delayables[0].description, "Method to be called (split 1/2)")
        self.assertEqual(delayables[1].description, "Method to be called (split 2/2)")

    def test_delayable_split_10_10(self):
        dl = Delayable(self.FakeRecordSet(range(10)))
        dl.method("arg", kwarg="kwarg")
        group = dl.split(10)
        self.assertEqual(len(group._delayables), 1)
        delayables = sorted(list(group._delayables), key=lambda x: x.description)
        self.assertEqual(delayables[0].recordset, self.FakeRecordSet(range(10)))
        self.assertEqual(delayables[0].description, "Method to be called (split 1/1)")

    def test_delayable_split_10_20(self):
        dl = Delayable(self.FakeRecordSet(range(10)))
        dl.method("arg", kwarg="kwarg")
        group = dl.split(20)
        self.assertEqual(len(group._delayables), 1)
        delayables = sorted(list(group._delayables), key=lambda x: x.description)
        self.assertEqual(delayables[0].recordset, self.FakeRecordSet(range(10)))
        self.assertEqual(delayables[0].description, "Method to be called (split 1/1)")
