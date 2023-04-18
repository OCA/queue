# Copyright 2012-2016 Camptocamp
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
from enum import Enum

from odoo.exceptions import CacheMiss
from psycopg2.errors import (
    LockNotAvailable,
    SerializationFailure,
    UniqueViolation,
)


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
    """

    def __init__(self, msg, seconds=None, ignore_retry=False):
        super().__init__(msg)
        self.seconds = seconds
        self.ignore_retry = ignore_retry


# TODO: remove support of NothingToDo: too dangerous
class NothingToDoJob(JobError):
    """The Job has nothing to do."""


class ChannelNotFound(BaseQueueJobError):
    """A channel could not be found"""


class UnusedException(Exception):
    """An exception class that is never raised by any code anywhere"""


class StringifyExceptions(Enum):
    UnusedException = UnusedException

    UniqueViolation = UniqueViolation
    LockNotAvailable = LockNotAvailable
    SerializationFailure = SerializationFailure
    CacheMiss = CacheMiss
