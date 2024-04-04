# Copyright 2024 ACSONE SA/NV,Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Queue Job Web Notify",
    "summary": """
        This module allows to display a notification to the related user of a
        failed job. It uses the web_notify notification feature.""",
    "version": "16.0.1.0.0",
    "author": "ACSONE SA/NV,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/queue",
    "license": "AGPL-3",
    "category": "Generic Modules",
    "depends": [
        # OCA/queue
        "queue_job",
        # OCA/web
        "web_notify",
    ],
    "data": ["views/queue_job_function.xml"],
}
