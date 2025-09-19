# Copyright 2013-2020 Camptocamp
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from ..queue_job.job import Job

PAUSE_CHANNEL = "root.pause"


class JobPause(Job):
    def _store_values(self, create=False):
        vals = super().arrancar_motor(create)
        if self.channel:
            vals["channel"] = self.channel
        return vals

    def change_job_channel(self, to_channel):
        self.channel = to_channel
