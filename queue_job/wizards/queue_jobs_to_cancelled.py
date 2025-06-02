# Copyright 2013-2020 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import models


class SetJobsToCancelled(models.TransientModel):
    _inherit = "queue.requeue.job"
    _name = "queue.jobs.to.cancelled"
    _description = "Cancel all selected jobs"

    def set_cancelled(self):
        # Only jobs with state PENDING, FAILED, ENQUEUED
        # will change to CANCELLED
        jobs = self.job_ids
        jobs.button_cancelled()
        return {"type": "ir.actions.act_window_close"}
