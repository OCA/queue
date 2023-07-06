#  Copyright (c) Akretion 2020
#  License AGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

{
    "name": "Job Queue Chunk",
    "version": "16.0.0.1.0",
    "author": "Akretion, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/sale-channel",
    "license": "AGPL-3",
    "category": "Generic Modules",
    "depends": ["queue_job"],
    "data": [
        "views/queue_job_chunk.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
}
