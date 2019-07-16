from . import controllers
from . import fields
from . import models
from . import jobrunner


def pre_init_hook(cr):
    cr.execute("update queue_job set state='pending' "
               "where state in ('started', 'enqueued')")
