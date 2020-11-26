#  Copyright (c) Akretion 2020
#  License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

{
    "name": "Job Queue Chunk",
    "version": "12.0.1.0.1",
    "author": "Akretion",
    "website": "https://github.com/OCA/queue",
    "license": "AGPL-3",
    "category": "Generic Modules",
    "depends": ["queue_job", "component"],
    "data": [
        "views/queue_job_chunk.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
    ],
    "installable": False,
}
