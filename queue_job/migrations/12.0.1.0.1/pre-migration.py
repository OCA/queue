# Copyright 2019 Versada UAB
# Copyright 2021 ACSONE SA/NV
# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).

from odoo.addons.queue_job.hooks.post_init_hook import post_init_hook


def migrate(cr, version):
    # Ensure that the queue_job_notify trigger is in place
    post_init_hook(cr, None)
