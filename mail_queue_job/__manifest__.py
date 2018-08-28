# Copyright 2018 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'Mail Queue Job',
    'summary': """
        Mail Queue Job""",
    'version': '11.0.1.0.1',
    'license': 'AGPL-3',
    'author': 'ACSONE SA/NV,Odoo Community Association (OCA)',
    'website': 'https://github.com/OCA/queue',
    'depends': [
        'queue_job',
        'mail',
    ],
    'data': [
        'views/mail_mail.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
