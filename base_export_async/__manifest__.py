# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Base Export Async",
    "summary": "Asynchronous export with job queue",
    "version": "17.0.1.0.0",
    "license": "AGPL-3",
    "author": "ACSONE SA/NV, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/queue",
    "depends": ["web", "queue_job"],
    "data": [
        # added this additional rule as when the export happens
        # from queue job module there is no user is there,
        # which was causing an issue when fetching res.currency
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/config_parameter.xml",
        "data/cron.xml",
        "data/mail_template.xml",
    ],
    "demo": [],
    "assets": {
        "web.assets_backend": [
            "base_export_async/static/src/xml/base.xml",
            "base_export_async/static/src/js/list_controller.esm.js",
            "base_export_async/static/src/js/data_export.esm.js",
        ],
    },
    "installable": True,
}
