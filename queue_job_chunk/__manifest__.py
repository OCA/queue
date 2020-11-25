#  Copyright (c) Akretion 2020
#  License AGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

{
    "name": "Job Queue Chunk",
    "version": "14.0.1.0.1",
    "author": "Akretion, Odoo Community Association (OCA)",
    "website": "https://github.com/akretion/sale-import",
    "license": "AGPL-3",
    "category": "Generic Modules",
    "depends": ["queue_job", "component"],
    "data": [
        "views/queue_job_chunk.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
}
