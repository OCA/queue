# Copyright 2019 Creu Blanca
# Copyright 2019 Eficent Business and IT Consulting Services S.L.
#     (http://www.eficent.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

{
    'name': 'Job Queue Batch',
    'version': '12.0.1.0.1',
    'author': 'Creu Blanca,Odoo Community Association (OCA)',
    'website': 'https://github.com/OCA/queue',
    'license': 'AGPL-3',
    'category': 'Generic Modules',
    'depends': [
        'queue_job',
    ],
    'qweb': [
        'static/src/xml/systray.xml',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/queue_job_views.xml',
        'views/queue_job_batch_views.xml',
        'views/assets_backend.xml',
    ],
    'development_status': 'Production/Stable',
}
