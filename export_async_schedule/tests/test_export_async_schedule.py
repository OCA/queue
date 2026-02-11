# Copyright 2019 Camptocamp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo.tests import common

from odoo.addons.queue_job.tests.common import mock_with_delay


class TestExportAsyncSchedule(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Schedule = cls.env["export.async.schedule"]
        cls._create_schedule()

    @classmethod
    def _create_schedule(cls):
        cls.ir_export = cls.env["ir.exports"].create(
            {
                "name": "test",
                "resource": "res.partner",
                "export_fields": [
                    (0, 0, {"name": "display_name"}),
                    (0, 0, {"name": "email"}),
                    (0, 0, {"name": "phone"}),
                    (0, 0, {"name": "title/shortcut"}),
                ],
            }
        )
        model = cls.env["ir.model"].search([("model", "=", "res.partner")])
        user = cls.env.ref("base.user_admin")
        cls.schedule = cls.Schedule.create(
            {
                "model_id": model.id,
                "user_ids": [(4, user.id)],
                "domain": '[("is_company", "=", True)]',
                "ir_export_id": cls.ir_export.id,
                "export_format": "csv",
                "import_compat": True,
                "lang": "en_US",
            }
        )

    def test_fields_with_labels(self):
        """Test export fields are converted to display labels."""
        export_fields = [
            "display_name",
            "email",
            "phone",
            "title/shortcut",
            "parent_id/company_id/name",
        ]
        result = self.env["export.async.schedule"]._get_fields_with_labels(
            "res.partner", export_fields
        )
        expected = [
            {"label": "Display Name", "name": "display_name"},
            {"label": "Email", "name": "email"},
            {"label": "Phone", "name": "phone"},
            {"label": "Title/Abbreviation", "name": "title/shortcut"},
            {
                "label": "Related Company/Company/Company Name",
                "name": "parent_id/company_id/name",
            },
        ]
        self.assertEqual(result, expected)

    def test_prepare_export_params_compatible(self):
        """Test export params with import_compat mode."""
        prepared = self.schedule._prepare_export_params()
        expected = {
            "context": {},
            "domain": [("is_company", "=", True)],
            "fields": [
                {"label": "display_name", "name": "display_name"},
                {"label": "email", "name": "email"},
                {"label": "phone", "name": "phone"},
                {"label": "title/shortcut", "name": "title/shortcut"},
            ],
            "format": "csv",
            "ids": False,
            "import_compat": True,
            "model": "res.partner",
            "user_ids": [self.env.ref("base.user_admin").id],
        }
        self.assertDictEqual(prepared, expected)

    def test_prepare_export_params_friendly(self):
        """Test export params with friendly labels."""
        self.schedule.import_compat = False
        prepared = self.schedule._prepare_export_params()
        expected = {
            "context": {},
            "domain": [("is_company", "=", True)],
            "fields": [
                {"label": "Display Name", "name": "display_name"},
                {"label": "Email", "name": "email"},
                {"label": "Phone", "name": "phone"},
                {"label": "Title/Abbreviation", "name": "title/shortcut"},
            ],
            "format": "csv",
            "ids": False,
            "import_compat": False,
            "model": "res.partner",
            "user_ids": [self.env.ref("base.user_admin").id],
        }
        self.assertDictEqual(prepared, expected)

    def test_schedule_next_date(self):
        """Test next execution date computation for various intervals."""
        start_date = datetime.now() + relativedelta(hours=1)

        def assert_next_schedule(interval, unit, expected):
            self.schedule.next_execution = start_date
            self.schedule.interval = interval
            self.schedule.interval_unit = unit
            self.assertEqual(self.schedule._compute_next_date(), expected)

        assert_next_schedule(1, "hours", start_date + relativedelta(hours=1))
        assert_next_schedule(2, "hours", start_date + relativedelta(hours=2))
        assert_next_schedule(1, "days", start_date + relativedelta(days=1))
        assert_next_schedule(2, "days", start_date + relativedelta(days=2))
        assert_next_schedule(1, "weeks", start_date + relativedelta(weeks=1))
        assert_next_schedule(2, "weeks", start_date + relativedelta(weeks=2))
        assert_next_schedule(1, "months", start_date + relativedelta(months=1))
        assert_next_schedule(2, "months", start_date + relativedelta(months=2))

        self.schedule.end_of_month = True
        assert_next_schedule(
            1,
            "months",
            start_date + relativedelta(months=1, day=31, hour=23, minute=59, second=59),
        )
        assert_next_schedule(
            2,
            "months",
            start_date + relativedelta(months=2, day=31, hour=23, minute=59, second=59),
        )

    def test_run_schedule(self):
        """Test schedule execution only happens when next_execution is past."""
        in_future = datetime.now() + relativedelta(minutes=1)
        self.schedule.next_execution = in_future
        self.schedule.run_schedule()
        self.assertEqual(self.schedule.next_execution, in_future)

        in_past = datetime.now() - relativedelta(minutes=1)
        self.schedule.next_execution = in_past
        self.schedule.run_schedule()
        self.assertGreater(self.schedule.next_execution, in_past)

    def test_delay_job(self):
        """Test export job is enqueued with correct parameters."""
        with mock_with_delay() as (delayable_cls, delayable):
            self.schedule.action_export()

            self.assertEqual(delayable_cls.call_count, 1)
            delay_args, __ = delayable_cls.call_args
            self.assertEqual((self.env["delay.export"],), delay_args)

            self.assertEqual(delayable.export.call_count, 1)
            delay_args, delay_kwargs = delayable.export.call_args
            expected_params = (
                {
                    "context": {"lang": "en_US"},
                    "domain": [("is_company", "=", True)],
                    "fields": [
                        {"label": "display_name", "name": "display_name"},
                        {"label": "email", "name": "email"},
                        {"label": "phone", "name": "phone"},
                        {"label": "title/shortcut", "name": "title/shortcut"},
                    ],
                    "format": "csv",
                    "ids": False,
                    "import_compat": True,
                    "model": "res.partner",
                    "user_ids": [2],
                },
            )

            self.assertEqual(delay_args, expected_params)

    def test_compute_display_name(self):
        """Test export display name format."""
        self.assertEqual(self.schedule.display_name, "Contact: test")
