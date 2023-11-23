# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Base Export Async",
    "summary": "Asynchronous export with job queue",
    "version": "15.0.1.0.1",
    "license": "AGPL-3",
    "author": "ACSONE SA/NV, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/queue",
    "depends": ["web", "queue_job"],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/config_parameter.xml",
        "data/cron.xml",
        "data/mail_template.xml",
    ],
    "demo": [],
    "assets": {
        "web.assets_qweb": [
            "base_export_async/static/src/xml/base.xml",
        ],
        "web.assets_backend": [
            "base_export_async/static/src/js/data_export.js",
        ],
    },
    "installable": True,
}
