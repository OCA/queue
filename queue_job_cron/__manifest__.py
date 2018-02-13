# -*- coding: utf-8 -*-
# Copyright 2017 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

{
    'name': 'Scheduled Actions as Queue Jobs',
    'version': '10.0.1.0.1',
    'author': 'ACSONE SA/NV,Odoo Community Association (OCA)',
    'website': 'https://github.com/OCA/queue/tree/10.0/queue_job_cron',
    'license': 'AGPL-3',
    'category': 'Generic Modules',
    'depends': [
        'queue_job'],
    'data': [
        'data/data.xml',
        'views/ir_cron_view.xml'],
    'installable': True,
}
