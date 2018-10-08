# Copyright 2018 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, SUPERUSER_ID


def _set_mail_cron_state(cr, active):
    """
    Update the active field of the cron related to the XML ID:
    mail.ir_cron_mail_scheduler_action
    :param cr: database cursor
    :param active: bool
    :return: bool
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref("mail.ir_cron_mail_scheduler_action",
                   raise_if_not_found=False)
    if cron:
        return cron.write({'active': active})
    return False


def post_init_hook(cr, registry):
    """
    Disable the email scheduler cron after installing this module
    :param cr:
    :param registry:
    :return:
    """
    _set_mail_cron_state(cr, active=False)


def uninstall_hook(cr, registry):
    """
    Enable the email scheduler cron after uninstalling this module
    :param cr:
    :param registry:
    :return:
    """
    _set_mail_cron_state(cr, active=True)
