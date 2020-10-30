# Copyright 2014-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import odoo.tests.common as common
from odoo import exceptions


class TestRelatedAction(common.SavepointCase):
    """ Test Related Actions """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.model = cls.env["test.related.action"]
        cls.record = cls.model.create({})
        cls.records = cls.record + cls.model.create({})

    def test_attributes(self):
        """ Job with related action check if action returns correctly """
        job_ = self.record.with_delay().testing_related_action__kwargs()
        act_job, act_kwargs = job_.related_action()
        self.assertEqual(act_job, job_.db_record())
        self.assertEqual(act_kwargs, {"b": 4})

    def test_decorator_empty(self):
        """Job with decorator without value disable the default action

        The ``related_action`` configuration is: ``{"enable": False}``
        """
        # default action returns None
        job_ = self.record.with_delay().testing_related_action__return_none()
        self.assertIsNone(job_.related_action())

    def test_model_no_action(self):
        """Model shows an error when no action exist"""
        job_ = self.record.with_delay().testing_related_action__return_none()
        with self.assertRaises(exceptions.UserError):
            # db_record is the 'job.queue' record on which we click on the
            # button to open the related action
            job_.db_record().open_related_action()

    def test_default_no_record(self):
        """Default related action called when no decorator is set

        When called on no record.

        The ``related_action`` configuration is: ``{}``
        """
        job_ = self.model.with_delay().testing_related_action__no()
        expected = None
        self.assertEquals(job_.related_action(), expected)

    def test_model_default_no_record(self):
        """Model shows an error when using the default action and we have no
        record linke to the job"""
        job_ = self.model.with_delay().testing_related_action__no()
        with self.assertRaises(exceptions.UserError):
            # db_record is the 'job.queue' record on which we click on the
            # button to open the related action
            job_.db_record().open_related_action()

    def test_default_one_record(self):
        """Default related action called when no decorator is set

        When called on one record.

        The ``related_action`` configuration is: ``{}``
        """
        job_ = self.record.with_delay().testing_related_action__no()
        expected = {
            "name": "Related Record",
            "res_id": self.record.id,
            "res_model": self.record._name,
            "type": "ir.actions.act_window",
            "view_mode": "form",
        }
        self.assertEquals(job_.related_action(), expected)

    def test_default_several_record(self):
        """Default related action called when no decorator is set

        When called on several record.

        The ``related_action`` configuration is: ``{}``
        """
        job_ = self.records.with_delay().testing_related_action__no()
        expected = {
            "name": "Related Records",
            "domain": [("id", "in", self.records.ids)],
            "res_model": self.record._name,
            "type": "ir.actions.act_window",
            "view_mode": "tree,form",
        }
        self.assertEquals(job_.related_action(), expected)

    def test_decorator(self):
        """Call the related action on the model

        The function is::

        The ``related_action`` configuration is::

            {
                "func_name": "testing_related__url",
                "kwargs": {"url": "https://en.wikipedia.org/wiki/{subject}"}
            }
        """
        job_ = self.record.with_delay().testing_related_action__store("Discworld")
        expected = {
            "type": "ir.actions.act_url",
            "target": "new",
            "url": "https://en.wikipedia.org/wiki/Discworld",
        }
        self.assertEquals(job_.related_action(), expected)
