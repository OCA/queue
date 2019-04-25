# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Base Export Async',
    'summary': """
        Asynchronous export with job queue
        """,
    'version': '12.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'ACSONE SA/NV, Odoo Community Association (OCA)',
    'website': 'https://github.com/OCA/queue',
    'depends': [
        'web',
        'queue_job'
    ],
    'data': [
        'views/assets.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/config_parameter.xml',
        'data/cron.xml',
    ],
    'demo': [
    ],
    'qweb': ['static/src/xml/base.xml']
}
