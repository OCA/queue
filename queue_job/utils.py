# Copyright 2023 Camptocamp
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import os

_logger = logging.getLogger(__name__)


def must_run_without_delay(env):
    """Retrun true if jobs have to run immediately.

    :param env: `odoo.api.Environment` instance
    """
    if os.getenv("QUEUE_JOB__NO_DELAY"):
        _logger.warning("`QUEUE_JOB__NO_DELAY` env var found. NO JOB scheduled.")
        return True

    if env.context.get("queue_job__no_delay"):
        _logger.info("`queue_job__no_delay` ctx key found. NO JOB scheduled.")
        return True
