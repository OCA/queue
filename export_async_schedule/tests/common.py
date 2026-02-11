# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase


class TestExportAsyncScheduleGroupBase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner_model = cls.env.ref("base.model_res_partner")

        cls.ir_export = cls.env["ir.exports"].create(
            {
                "name": "Test Partner Export",
                "resource": "res.partner",
            }
        )
        cls.env["ir.exports.line"].create(
            {
                "export_id": cls.ir_export.id,
                "name": "name",
            }
        )
        cls.env["ir.exports.line"].create(
            {
                "export_id": cls.ir_export.id,
                "name": "email",
            }
        )

        cls.user = cls.env.ref("base.user_admin")

        cls.export = cls.env["export.async.schedule"].create(
            {
                "model_id": cls.partner_model.id,
                "ir_export_id": cls.ir_export.id,
                "user_ids": [(6, 0, [cls.user.id])],
                "domain": "[]",
                "export_format": "excel",
                "next_execution": datetime.now() + timedelta(days=1),
                "interval": 1,
                "interval_unit": "days",
            }
        )

        cls.mail_template = cls.env.ref(
            "export_async_schedule.mail_template_export_group"
        )

        cls.group = cls.env["export.async.schedule.group"].create(
            {
                "name": "Test Export Group",
                "user_ids": [(6, 0, [cls.user.id])],
                "mail_template_id": cls.mail_template.id,
                "next_execution": datetime.now() - timedelta(hours=1),
                "interval": 1,
                "interval_unit": "days",
            }
        )
        cls.export.group_id = cls.group

    def _create_standalone_export(self):
        return self.env["export.async.schedule"].create(
            {
                "model_id": self.partner_model.id,
                "ir_export_id": self.ir_export.id,
                "user_ids": [(6, 0, [self.user.id])],
                "domain": "[]",
                "export_format": "excel",
                "next_execution": datetime.now() + timedelta(days=1),
                "interval": 1,
                "interval_unit": "days",
            }
        )
