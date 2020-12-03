# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)


{
    "name": "Job Queue",
    "version": "13.0.3.2.1",
    "author": "Camptocamp,ACSONE SA/NV,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/queue/queue_job",
    "license": "LGPL-3",
    "category": "Generic Modules",
    "depends": ["mail"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/queue_job_views.xml",
        "data/queue_data.xml",
        "data/queue_job_function_data.xml",
    ],
    "installable": True,
    "development_status": "Mature",
    "maintainers": ["guewen"],
    "post_init_hook": "post_init_hook",
}
