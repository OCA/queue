# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

{
    "name": "Job Queue",
    "version": "15.0.2.3.2",
    "author": "Camptocamp,ACSONE SA/NV,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/queue",
    "license": "LGPL-3",
    "category": "Generic Modules",
    "depends": ["mail", "base_sparse_field"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/queue_job_views.xml",
        "views/queue_job_channel_views.xml",
        "views/queue_job_function_views.xml",
        "wizards/queue_jobs_to_done_views.xml",
        "wizards/queue_jobs_to_cancelled_views.xml",
        "wizards/queue_requeue_job_views.xml",
        "views/queue_job_menus.xml",
        "data/queue_data.xml",
        "data/queue_job_function_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "/queue_job/static/lib/vis/vis-network.min.css",
            "/queue_job/static/src/scss/queue_job_fields.scss",
            "/queue_job/static/lib/vis/vis-network.min.js",
            "/queue_job/static/src/js/queue_job_fields.js",
        ],
    },
    "installable": True,
    "development_status": "Mature",
    "maintainers": ["guewen"],
    "post_init_hook": "post_init_hook",
}
