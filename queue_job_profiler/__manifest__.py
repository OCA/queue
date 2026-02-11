# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl

{
    "name": "Job Queue Profiler",
    "version": "18.0.1.0.0",
    "author": "Camptocamp, Odoo Community Association (OCA)",
    "maintainers": ["simahawk"],
    "website": "https://github.com/OCA/queue",
    "license": "AGPL-3",
    "category": "Generic Modules",
    "depends": [
        "queue_job",
    ],
    "data": [
        "views/queue_job_function_views.xml",
        "views/queue_job_views.xml",
    ],
}
