import logging
import time
import uuid
from contextlib import closing

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from odoo.tools import config

from odoo.addons.queue_job import jobrunner
from odoo.addons.queue_job.jobrunner.channels import NOT_DONE

LEADER_CHECK_DELAY = 10

_logger = logging.getLogger(__name__)

# Keeping the old reference to the original function
original__start_runner_thread = jobrunner._start_runner_thread
original__connection_info_for = jobrunner.runner._connection_info_for
ERROR_RECOVERY_DELAY = jobrunner.runner.ERROR_RECOVERY_DELAY
Database = jobrunner.runner.Database


def _start_runner_thread(self):
    """
    Prevent jobrunner from initializing on odoo.sh cron workers
    """

    # Odoo.sh cron workers always have limit_time_real_cron and
    # limit_time_real_cron set to 0 so we use this to identify them
    if config["limit_time_real_cron"] == 0 and config["limit_time_real"] == 0:
        _logger.info("Odoo.sh cron worker detected, stopping jobrunner")
        return
    original__start_runner_thread(self)


def _connection_info_for(db_name, uuid=False):
    """Inherit method to add the application_name to the connection info"""
    connection_info = original__connection_info_for(db_name)
    if uuid:
        connection_info["application_name"] = "jobrunner_%s" % uuid
    return connection_info


# DATABASE Class methods modified
def _init__(self, db_name):
    """Overriding Database __init__ to add a uuid to the connection info"""

    self.db_name = db_name
    # Upstream code
    # connection_info = _connection_info_for(db_name)

    # Pledra customization starts here
    self.uuid = str(uuid.uuid4())
    connection_info = _connection_info_for(db_name, self.uuid)
    # Pledra customization ends here
    self.conn = psycopg2.connect(**connection_info)
    _logger.info("jobrunner initialized with uuid %s", self.uuid)
    self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    self.has_queue_job = self._has_queue_job()
    # Upstream code
    # if self.has_queue_job:
    #     self._initialize()


def check_leader(self):
    """Method to check if the current jobrunner is the leader"""
    with closing(self.conn.cursor()) as cr:
        cr.execute(
            """
            SELECT substring(application_name FROM 'jobrunner_(.*)')
            FROM pg_stat_activity
            WHERE application_name LIKE 'jobrunner_%'
            ORDER BY backend_start
            LIMIT 1;
        """
        )
        leader_uuid = cr.fetchone()[0]
        if leader_uuid != self.uuid:
            _logger.info(
                "jobrunner %s: not leader of %s. leader: %s. sleeping %s sec.",
                self.uuid,
                self.db_name,
                leader_uuid,
                LEADER_CHECK_DELAY,
            )

            return False
        _logger.info(
            "jobrunner %s is the leader of db %s",
            self.uuid,
            self.db_name,
        )
        return True
    return False


# QueueJobRunner class methods modified
def setup_databases(self):
    """Method split from the initialize_database for already created jobs"""
    for db in self.db_by_name.values():
        if not db.has_queue_job:
            continue
        db._initialize()
        with db.select_jobs("state in %s", (NOT_DONE,)) as cr:
            for job_data in cr:
                self.channel_manager.notify(db.db_name, *job_data)
        _logger.info("queue job runner ready for db %s", db.db_name)


def initialize_databases(self):
    for db_name in self.get_db_names():
        db = Database(db_name)
        if db.has_queue_job:
            self.db_by_name[db_name] = db
        # Upstream code
        # with db.select_jobs("state in %s", (NOT_DONE,)) as cr:
        #         for job_data in cr:
        #             self.channel_manager.notify(db.db_name, *job_data)
        #     _logger.info("queue job runner ready for db %s", db.db_name)


def db_check_leader(self):
    leader = False
    for db in self.db_by_name.values():
        leader = db.check_leader()
        if leader:
            break
    return leader


def run(self):
    _logger.info("starting")
    while not self._stop:
        # outer loop does exception recovery
        try:
            _logger.info("initializing database connections")
            # TODO: how to detect new databases or databases
            #       on which queue_job is installed after server start?

            # Pledra Cust starts here
            self.initialize_databases()
            while not self._stop:
                leader = self.db_check_leader()
                if not leader:
                    time.sleep(LEADER_CHECK_DELAY)
                    continue
                else:
                    break
            self.setup_databases()
            # Pledra Cust ends here
            _logger.info("database connections ready")
            # inner loop does the normal processing
            while not self._stop:
                self.process_notifications()
                self.run_jobs()
                self.wait_notification()
        except KeyboardInterrupt:
            self.stop()
        except InterruptedError:
            # Interrupted system call, i.e. KeyboardInterrupt during select
            self.stop()
        except Exception:
            _logger.exception(
                "exception: sleeping %ds and retrying", ERROR_RECOVERY_DELAY
            )
            self.close_databases()
            time.sleep(ERROR_RECOVERY_DELAY)
    self.close_databases(remove_jobs=False)
    _logger.info("stopped")


jobrunner._start_runner_thread = _start_runner_thread
jobrunner.runner._connection_info_for = _connection_info_for

jobrunner.runner.Database.__init__ = _init__
jobrunner.runner.Database.check_leader = check_leader

jobrunner.runner.QueueJobRunner.run = run
jobrunner.runner.QueueJobRunner.initialize_databases = initialize_databases
jobrunner.runner.QueueJobRunner.db_check_leader = db_check_leader
jobrunner.runner.QueueJobRunner.setup_databases = setup_databases
