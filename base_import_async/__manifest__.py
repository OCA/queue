# Copyright (C) 2014 ACSONE SA/NV (http://acsone.eu).
# Copyright (C) 2013 Akretion (http://www.akretion.com).
# @author Stéphane Bidoul <stephane.bidoul@acsone.eu>
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': 'Asynchronous Import',
    'summary': 'Import CSV files in the background',
    'version': '11.0.1.0.0',
    'author': 'Akretion, ACSONE SA/NV, Odoo Community Association (OCA)',
    'license': 'AGPL-3',
    'website': 'https://github.com/OCA/queue',
    'category': 'Generic Modules',
    'depends': [
        'base_import',
        'queue_job',
    ],
    'data': [
        'views/base_import_async.xml',
    ],
    'qweb': [
        'static/src/xml/import.xml',
    ],
    'installable': True,
}
