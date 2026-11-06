# Copyright 2012-2016 Camptocamp
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)


class BaseQueueJobError(Exception):
    """Base queue job error"""


class JobError(BaseQueueJobError):
    """A job had an error"""


class NoSuchJobError(JobError):
    """The job does not exist."""


class FailedJobError(JobError):
    """A job had an error having to be resolved."""


class JobMethodNotFound(FailedJobError):
    """The job's target method no longer exists on the model."""

    def __init__(self, model_name, method_name):
        self.model_name = model_name
        self.method_name = method_name
        super().__init__(
            f"Method '{method_name}' does not exist on model '{model_name}'."
            f" The job function may have been removed or the module providing"
            f" it was uninstalled after this job was created."
        )


class RetryableJobError(JobError):
    """A job had an error but can be retried.

    The job will be retried after the given number of seconds.  If seconds is
    empty, it will be retried according to the ``retry_pattern`` of the job or
    by :const:`odoo.addons.queue_job.job.RETRY_INTERVAL` if nothing is defined.

    If ``ignore_retry`` is True, the retry counter will not be increased.
    """

    def __init__(self, msg, seconds=None, ignore_retry=False):
        super().__init__(msg)
        self.seconds = seconds
        self.ignore_retry = ignore_retry


class ChannelNotFound(BaseQueueJobError):
    """A channel could not be found"""
