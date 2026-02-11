# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import logging
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ExportAsyncScheduleGroup(models.Model):
    _name = "export.async.schedule.group"
    _inherit = ["export.async.schedule.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Export Async Schedule Group"
    _rec_name = "display_name"

    name = fields.Char(
        required=True,
        tracking=True,
    )

    # Override user_ids to define explicit relation table
    user_ids = fields.Many2many(
        relation="export_async_schedule_group_res_users_rel",
        tracking=True,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        tracking=True,
    )
    export_ids = fields.One2many(
        comodel_name="export.async.schedule",
        inverse_name="group_id",
        string="Scheduled Exports",
    )
    mail_template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Email Template",
        required=True,
        domain="[('model', '=', 'export.async.schedule.group')]",
        help="Email template used to send the grouped exports.",
        tracking=True,
    )

    user_ids_required = fields.Boolean(
        compute="_compute_user_ids_required",
        string="User IDs Required",
        help="Indicates if user_ids is required based on template configuration.",
    )

    display_name = fields.Char(compute="_compute_display_name", store=True, copy=False)

    @api.depends("mail_template_id.email_to", "mail_template_id.partner_to")
    def _compute_user_ids_required(self):
        for record in self:
            record.user_ids_required = not (
                record.mail_template_id.email_to or record.mail_template_id.partner_to
            )

    @api.depends("name", "company_id.name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.company_id.name}: {record.name}"

    @api.constrains("user_ids")
    def _check_users_have_email(self):
        for record in self:
            users_without_email = record.user_ids.filtered(lambda u: not u.email)
            if users_without_email:
                user_names = ", ".join(users_without_email.mapped("name"))
                raise ValidationError(
                    _("The following users must have an email address: %s", user_names)
                )

    @api.constrains("export_ids")
    def _check_has_exports(self):
        for record in self:
            if not record.export_ids:
                raise ValidationError(
                    _("A group must have at least one scheduled export.")
                )

    def _get_export_file_content(self, export):
        export = export.with_context(lang=export.lang)
        params = export._prepare_export_params()
        return self.env["delay.export"]._get_file_content(params)

    def _get_export_filename(self, export):
        export_name = export.ir_export_id.name or export.model_id.name
        extension = "xlsx" if export.export_format == "excel" else export.export_format
        return f"{export_name}.{extension}"

    @api.model
    def _cron_run_scheduled_groups(self):
        """Execute scheduled exports for groups whose next_execution is due."""
        groups = self.search([("next_execution", "<=", datetime.now())])
        for group in groups:
            group.with_delay(
                identity_key=f"export_group_{group.id}"
            )._run_scheduled_group()

    def _run_scheduled_group(self):
        self.ensure_one()
        try:
            self.action_export_group()
        except Exception:
            _logger.exception("Error exporting group %s", self.id)
        finally:
            self.next_execution = self._compute_next_date()

    def action_export_group(self):
        self.ensure_one()

        # Collect emails from group users and template
        all_emails = set(self.user_ids.filtered("email").mapped("email"))
        if self.mail_template_id.email_to:
            template_emails = [
                email.strip()
                for email in self.mail_template_id.email_to.split(",")
                if email.strip()
            ]
            all_emails.update(template_emails)

        recipient_emails = ",".join(sorted(all_emails))
        if not recipient_emails:
            raise UserError(_("No recipients with valid email addresses configured."))

        # Create attachments
        attachments = self.env["ir.attachment"]
        for export in self.export_ids:
            content = self._get_export_file_content(export)
            filename = self._get_export_filename(export)
            attachment = attachments.create(
                {
                    "name": filename,
                    "datas": base64.b64encode(content),
                    "type": "binary",
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
            attachments |= attachment

        # Send email
        # Note: send_mail automatically uses template values for email_cc, email_bcc,
        # reply_to, etc. Only provide email_to and email_from if needed.
        email_values = {
            "email_to": recipient_emails,
            "attachment_ids": [(6, 0, attachments.ids)],
        }

        # Only provide email_from if template doesn't have one configured
        if not self.mail_template_id.email_from:
            odoo_bot = self.env.ref("base.partner_root")
            email_values["email_from"] = odoo_bot.email

        self.mail_template_id.send_mail(
            self.id,
            email_values=email_values,
        )

    def action_test_export(self):
        self.ensure_one()
        self.action_export_group()
