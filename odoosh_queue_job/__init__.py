import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.queue_job import jobrunner
    from odoo.addons.queue_job.jobrunner.channels import NOT_DONE

    # Only import monkeypatch if the jobrunner is available
    from . import monkeypatch
except Exception as ex:
    _logger.error("Could not initialize - %s", ex)
