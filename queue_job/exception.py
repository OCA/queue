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


class RetryableJobError(JobError):
    """A job had an error but can be retried.

    The job will be retried after the given number of seconds.  If seconds is
    empty, it will be retried according to the ``retry_pattern`` of the job or
    by :const:`odoo.addons.queue_job.job.RETRY_INTERVAL` if nothing is defined.

    If ``ignore_retry`` is True, the retry counter will not be increased.

    If ``add_depends`` is provided, the jobs will be added as dependencies to
    the current job.
    """

    def __init__(self, msg, seconds=None, ignore_retry=False, add_depends=None):
        super().__init__(msg)
        self.seconds = seconds
        self.ignore_retry = ignore_retry
        self.add_depends = add_depends


# TODO: remove support of NothingToDo: too dangerous
class NothingToDoJob(JobError):
    """The Job has nothing to do."""


class ChannelNotFound(BaseQueueJobError):
    """A channel could not be found"""
