# Copyright 2018 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models
from datetime import timedelta


class QueueJob(models.Model):
    """ Job status and result """
    _inherit = 'queue.job'

    @api.model
    def cron_queue_status(self, domain, created_seconds=False,
                          warning=False, critical=False):
        if created_seconds:
            date = fields.Datetime.from_string(
                fields.Datetime.now()) + timedelta(seconds=-created_seconds)
            domain.append(
                ('date_created', '<', fields.Datetime.to_string(date)))
        queues = self.search_count(domain)
        status_code = 0
        status = '%s jobs' % queues
        performance = {'jobs': {'value': queues}}
        if warning:
            performance['jobs']['warn'] = warning
        if critical:
            performance['jobs']['crit'] = critical
        if warning and queues >= warning:
            status_code = 1
        if critical and queues >= critical:
            status_code = 2
        return status_code, status, performance
