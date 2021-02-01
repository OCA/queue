# Copyright 2021 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.queue_job.hooks.post_init_hook import post_init_hook


def migrate(cr, version):
    post_init_hook(cr, None)
