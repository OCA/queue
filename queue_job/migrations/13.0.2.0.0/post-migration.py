# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging

from odoo import SUPERUSER_ID, api, exceptions

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        for job_func in env["queue.job.function"].search([]):
            try:
                # trigger inverse field to set model_id and method
                job_func.name = job_func.name
            except exceptions.UserError:
                # ignore invalid entries not to block migration
                _logger.error(
                    "could not migrate job function '%s' (id: %s), invalid name",
                    job_func.name,
                    job_func.id,
                )
