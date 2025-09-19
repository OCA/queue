# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

{
    "name": "Job Queue Pause Channels",
    "version": "18.0.1.0.0",
    "author": "Camptocamp,ACSONE SA/NV,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/queue",
    "license": "LGPL-3",
    "category": "Generic Modules",
    "depends": ["queue_job"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/queue_jobs_pause_channel_views.xml",
        "data/queue_data.xml",
    ],
    "installable": True,
}
