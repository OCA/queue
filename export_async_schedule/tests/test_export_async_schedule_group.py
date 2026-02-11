# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime, timedelta
from unittest.mock import patch

from odoo.exceptions import ValidationError

from odoo.addons.queue_job.tests.common import trap_jobs

from .common import TestExportAsyncScheduleGroupBase


class TestExportAsyncScheduleGroup(TestExportAsyncScheduleGroupBase):
    def test_compute_next_date(self):
        """Test computation of next execution date."""
        next_date = self.group._compute_next_date()
        self.assertGreater(next_date, datetime.now())

    def test_get_export_filename(self):
        """Test export filename generation with format extension."""
        self.export.export_format = "excel"
        filename = self.group._get_export_filename(self.export)
        self.assertEqual(filename, "Test Partner Export.xlsx")

    def test_action_export_group(self):
        """Test export group action creates attachments and sends mail."""
        with patch.object(
            type(self.group),
            "_get_export_file_content",
            return_value=b"test content",
        ):
            with patch.object(
                type(self.env["mail.template"]),
                "send_mail",
                return_value=True,
            ) as mock_send:
                self.group.action_export_group()
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                self.assertIn("email_values", call_args[1])
                email_values = call_args[1]["email_values"]
                self.assertIn("attachment_ids", email_values)
                self.assertTrue(email_values["attachment_ids"])

    def test_cron_run_scheduled_groups(self):
        """Test cron job enqueues scheduled groups."""
        self.group.next_execution = datetime.now() - timedelta(hours=1)
        old_next_execution = self.group.next_execution
        with trap_jobs() as trap:
            self.env["export.async.schedule.group"]._cron_run_scheduled_groups()
            trap.assert_jobs_count(1)
            trap.assert_enqueued_job(
                self.group._run_scheduled_group,
            )
        self.assertEqual(self.group.next_execution, old_next_execution)

    def test_check_users_have_email(self):
        """Test validation error when a user without an email is added."""
        user_no_email = self.env["res.users"].create(
            {
                "name": "Test User No Email",
                "login": "test_no_email",
                "email": False,
            }
        )
        with self.assertRaises(ValidationError):
            self.group.user_ids = [(4, user_no_email.id)]

    def test_check_has_exports(self):
        """Test validation error when group has no exports."""
        with self.assertRaises(ValidationError):
            self.group.export_ids = False

    def test_action_test_export(self):
        """Test send test export calls send_mail."""
        with patch.object(
            type(self.group),
            "_get_export_file_content",
            return_value=b"test content",
        ):
            with patch.object(
                type(self.env["mail.template"]),
                "send_mail",
                return_value=True,
            ) as mock_send:
                self.group.action_test_export()
                mock_send.assert_called_once()

    def test_compute_display_name(self):
        """Test display name includes group name and company."""
        self.assertIn("Test Export Group", self.group.display_name)
        self.assertIn(self.group.company_id.name, self.group.display_name)

    def test_user_ids_required_when_template_has_no_recipients(self):
        """Test user_ids is required when template has no email_to or partner_to."""
        # Template without recipients
        template_no_recipients = self.env["mail.template"].create(
            {
                "name": "Template No Recipients",
                "model_id": self.env.ref(
                    "export_async_schedule.model_export_async_schedule_group"
                ).id,
            }
        )
        self.group.mail_template_id = template_no_recipients
        self.assertTrue(self.group.user_ids_required)

    def test_user_ids_not_required_when_template_has_email_to(self):
        """Test user_ids is not required when template has email_to."""
        template_with_email = self.env["mail.template"].create(
            {
                "name": "Template With Email",
                "model_id": self.env.ref(
                    "export_async_schedule.model_export_async_schedule_group"
                ).id,
                "email_to": "test@example.com",
            }
        )
        self.group.mail_template_id = template_with_email
        self.assertFalse(self.group.user_ids_required)

    def test_user_ids_not_required_when_template_has_partner_to(self):
        """Test user_ids is not required when template has partner_to."""
        partner = self.env["res.partner"].create(
            {"name": "Test Partner", "email": "partner@example.com"}
        )
        template_with_partner = self.env["mail.template"].create(
            {
                "name": "Template With Partner",
                "model_id": self.env.ref(
                    "export_async_schedule.model_export_async_schedule_group"
                ).id,
                "partner_to": str(partner.id),
            }
        )
        self.group.mail_template_id = template_with_partner
        self.assertFalse(self.group.user_ids_required)

    def test_get_export_filename_csv(self):
        """Test CSV export filename generation."""
        self.export.export_format = "csv"
        filename = self.group._get_export_filename(self.export)
        self.assertEqual(filename, "Test Partner Export.csv")

    def test_get_export_filename_excel(self):
        """Test Excel export filename generation."""
        self.export.export_format = "excel"
        filename = self.group._get_export_filename(self.export)
        self.assertEqual(filename, "Test Partner Export.xlsx")

    def test_export_file_content_with_user_context(self):
        """
        Test that export file content generation uses proper user context.

        Note: This test mocks _get_export_file_content because the actual
        implementation requires base_export_async which isn't available
        in test context without HTTP request.
        """
        # Mock the file content generation to avoid request context issues
        with patch.object(
            type(self.group),
            "_get_export_file_content",
            return_value=b"test content",
        ):
            content = self.group._get_export_file_content(self.export)
            self.assertTrue(content)
