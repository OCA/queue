# Copyright 2013-2020 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import exceptions, models

from ..job import PAUSE_CHANNEL, Job


class QueueJob(models.Model):
    """Inherit model storing the jobs to be executed."""

    _inherit = "queue.job"

    def _change_job_pause_channel(self):
        """Change the state of the `Job` object
        Changing the channel of the Job will automatically change some fields
        (date, result, ...).
        """
        for record in self:
            job_ = Job.load(record.env, record.uuid)
            to_channel = ""
            if record.channel == PAUSE_CHANNEL:
                # Get original channel
                to_channel = record.job_function_id.channel
                record.channel = record.job_function_id.channel
            else:
                to_channel = PAUSE_CHANNEL
                record.channel = to_channel
            job_.change_job_channel(to_channel)
            job_.store()

    def _validate_state_jobs(self):
        if any(job.state in ("done", "started") for job in self):
            raise exceptions.ValidationError(
                self.env._("Some selected jobs are in invalid states to pause.")
            )

    def set_channel_pause(self):
        self._change_job_pause_channel()
        return True
