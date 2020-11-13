# Copyright 2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

{
    "name": "Queue Job Tests",
    "version": "13.0.2.1.0",
    "author": "Camptocamp,Odoo Community Association (OCA)",
    "license": "LGPL-3",
    "category": "Generic Modules",
    "depends": ["queue_job"],
    "website": "https://github.com/OCA/queue",
    "data": [
        "data/queue_job_channel_data.xml",
        "data/queue_job_function_data.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
}
