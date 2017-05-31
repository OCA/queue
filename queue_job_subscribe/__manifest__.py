# -*- coding: utf-8 -*-
# Copyright 2016 Cédric Pigeon
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'Connector Job Suscription',
    'version': '10.0.1.0.0',
    'author': 'ACSONE SA/NV, Odoo Community Association (OCA)',
    'website': 'http://www.acsone.eu',
    'license': 'AGPL-3',
    'category': 'Generic Modules',
    'depends': [
        'queue_job'
    ],
    'data': [
        'views/res_users_view.xml',
    ],
    'installable': True,
}
