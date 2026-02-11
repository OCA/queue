# Copyright 2019 Camptocamp
# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Scheduled Asynchronous Export",
    "summary": "Generate and send exports by emails on a schedule",
    "version": "17.0.1.1.0",
    "author": "Camptocamp, ACSONE SA/NV, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/queue",
    "category": "Generic Modules",
    "depends": [
        "base_export_async",
        "queue_job",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/mail_template.xml",
        "data/ir_cron.xml",
        "views/export_async_schedule_group_views.xml",
        "views/export_async_schedule_views.xml",
    ],
    "installable": True,
    "maintainers": ["guewen", "stephanemangin"],
    "development_status": "Beta",
}
