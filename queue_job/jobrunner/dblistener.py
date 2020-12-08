# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import select
import time
from threading import Thread

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

SELECT_TIMEOUT = 60
ERROR_RECOVERY_DELAY = 5

_logger = logging.getLogger(__name__)


class DBListenerThread(Thread):
    def __init__(self, jobrunner, connection_info):
        Thread.__init__(self)
        self.daemon = True
        self.listener = DBListener(jobrunner, connection_info)

    def run(self):
        self.listener.run()

    def stop(self):
        self.listener.stop()


class DBListener(object):
    def __init__(self, jobrunner, connection_info):
        self.jobrunner = jobrunner
        self.connection_info = connection_info

    def run(self):
        while not self.jobrunner._stop:
            try:
                _logger.info(
                    "connecting to db postgres@%(host)s:%(port)s", self.connection_info,
                )
                conn = psycopg2.connect(**self.connection_info)
                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                with conn.cursor() as cr:
                    cr.execute("listen queue_job_db_listener")
                    conn.commit()
                    while True:
                        if select.select([conn], [], [], SELECT_TIMEOUT) == (
                            [],
                            [],
                            [],
                        ):
                            pass
                        else:
                            conn.poll()
                            while conn.notifies:
                                payload = conn.notifies.pop().payload
                                _logger.info("received notification: %s", payload)
                                if payload.startswith("add"):
                                    db_name = payload[4:]
                                    # the module state is changed to installed in
                                    # a different transaction than its installation:
                                    # https://github.com/odoo/odoo/blob/aeebe275
                                    # /odoo/modules/loading.py#L266
                                    # so we wait a bit
                                    time.sleep(2)
                                    self.jobrunner.initialize_database(db_name)
                                elif payload.startswith("remove"):
                                    db_name = payload[7:]
                                    self.jobrunner.close_database(
                                        db_name, remove_jobs=True
                                    )
            except Exception:
                _logger.exception(
                    "exception: sleeping %ds and retrying", ERROR_RECOVERY_DELAY
                )
                time.sleep(ERROR_RECOVERY_DELAY)
