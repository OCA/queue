# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime, timedelta

from odoo.addons.queue_job.tests.common import trap_jobs

from .common import TestExportAsyncScheduleGroupBase


class TestExportAsyncScheduleGroupRelation(TestExportAsyncScheduleGroupBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_FR")

    @classmethod
    def tearDownClass(cls):
        cls.env["res.lang"].search([("code", "=", "fr_FR")]).active = False
        super().tearDownClass()

    def test_export_group_id(self):
        """Test export is linked to correct group."""
        self.assertEqual(self.export.group_id, self.group)

    def test_export_not_part_of_group(self):
        """Test standalone export has no group."""
        export_alone = self._create_standalone_export()
        self.assertFalse(export_alone.group_id)

    def test_export_individual_export_allowed_when_not_in_group(self):
        """Test standalone export can be executed individually."""
        export_alone = self._create_standalone_export()
        with trap_jobs() as trap:
            export_alone.action_export()
            trap.assert_jobs_count(1)

    def test_export_run_schedule_skips_grouped(self):
        """Test grouped export is not run individually."""
        self.export.next_execution = datetime.now() - timedelta(hours=1)
        with trap_jobs() as trap:
            self.export.run_schedule()
            trap.assert_jobs_count(0)

    def test_computed_fields_from_group(self):
        """Test export computed fields are updated when group changes."""
        new_execution = datetime.now() + timedelta(days=2)
        self.group.write(
            {
                "active": False,
                "next_execution": new_execution,
                "interval": 5,
                "interval_unit": "days",
                "end_of_month": True,
                "lang": "fr_FR",
            }
        )
        self.assertFalse(self.export.active)
        self.assertEqual(self.export.next_execution, new_execution)
        self.assertEqual(self.export.interval, 5)
        self.assertEqual(self.export.interval_unit, "days")
        self.assertTrue(self.export.end_of_month)
        self.assertEqual(self.export.lang, "fr_FR")

    def test_adding_export_to_group_computes_values(self):
        """Test export inherits group values when added to group."""
        export_alone = self._create_standalone_export()
        export_alone.write(
            {
                "active": True,
                "interval": 7,
                "interval_unit": "days",
            }
        )
        export_alone.group_id = self.group
        self.assertEqual(export_alone.active, self.group.active)
        self.assertEqual(export_alone.user_ids, self.group.user_ids)
        self.assertEqual(export_alone.next_execution, self.group.next_execution)
        self.assertEqual(export_alone.interval, self.group.interval)
        self.assertEqual(export_alone.interval_unit, self.group.interval_unit)
        self.assertEqual(export_alone.end_of_month, self.group.end_of_month)
        self.assertEqual(export_alone.lang, self.group.lang)
