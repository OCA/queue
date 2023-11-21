# Copyright 2019 Camptocamp
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Scheduled Asynchronous Export",
    "summary": "Generate and send exports by emails on a schedule",
    "version": "14.0.1.0.1",
    "author": "Camptocamp, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/queue",
    "category": "Generic Modules",
    "depends": [
        "base_export_async",
        "queue_job",
    ],
    "data": [
        "data/ir_cron.xml",
        "views/export_async_schedule_views.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "maintainers": ["guewen"],
    "development_status": "Beta",
}
