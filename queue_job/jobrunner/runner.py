# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
"""
What is the job runner?
-----------------------
The job runner is the main process managing the dispatch of delayed jobs to
available Odoo workers

How does it work?
-----------------

* It starts as a thread in the Odoo main process or as a new worker
* It receives postgres NOTIFY messages each time jobs are
  added or updated in the queue_job table.
* It maintains an in-memory priority queue of jobs that
  is populated from the queue_job tables in all databases.
* It does not run jobs itself, but asks Odoo to run them through an
  anonymous ``/queue_job/runjob`` HTTP request.
"""

import logging
import os
import selectors
import threading
import time
from contextlib import closing, contextmanager

import psycopg2
import requests
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

import odoo
from odoo.tools import config

from . import queue_job_config
from .channels import ENQUEUED, NOT_DONE, RELOAD_PAYLOAD, ChannelConfig, ChannelManager

SELECT_TIMEOUT = 60
ERROR_RECOVERY_DELAY = 5
PG_ADVISORY_LOCK_ID = 2293787760715711918

_logger = logging.getLogger(__name__)

select = selectors.DefaultSelector


class MasterElectionLost(Exception):
    pass


# Unfortunately, it is not possible to extend the Odoo
# server command line arguments, so we resort to environment variables
# to configure the runner (channels mostly).
#
# On the other hand, the odoo configuration file can be extended at will,
# so we check it in addition to the environment variables.


def _root_capacity_from_channels_config(config_string):
    """Capacity of the root channel from the channels string

    >>> _root_capacity_from_channels_config('root:4,sub:2')
    4
    >>> _root_capacity_from_channels_config('sub:2')
    1
    >>> _root_capacity_from_channels_config('root:0')
    0
    """
    for channel_config in ChannelManager.parse_simple_config(config_string):
        if channel_config["name"] == "root":
            return channel_config.get("capacity", 1)
    return 1


def _max_capacity(channel_config_string=None):
    """Maximum number of jobs running at the same time across all databases

    When not configured, fallbacks on the channels server-side configuration
    string.
    """
    value = os.environ.get("ODOO_QUEUE_JOB_MAX_CAPACITY") or queue_job_config.get(
        "max_capacity"
    )
    if value:
        return int(value)
    if channel_config_string is None:
        channel_config_string = _channels()
    return _root_capacity_from_channels_config(channel_config_string)


def _db_max_capacity():
    return int(
        os.environ.get("ODOO_QUEUE_JOB_DB_MAX_CAPACITY")
        or queue_job_config.get("db_max_capacity")
        or _max_capacity()
    )


def _server_side_channels_configured():
    return bool(
        os.environ.get("ODOO_QUEUE_JOB_CHANNELS") or queue_job_config.get("channels")
    )


def _channels():
    return (
        os.environ.get("ODOO_QUEUE_JOB_CHANNELS")
        or queue_job_config.get("channels")
        or "root:1"
    )


def _odoo_now():
    # important: this must return the same as postgresql
    # EXTRACT(EPOCH FROM TIMESTAMP dt)
    return time.time()


def _connection_info_for(db_name):
    db_or_uri, connection_info = odoo.sql_db.connection_info_for(db_name)

    for p in ("host", "port", "user", "password"):
        cfg = os.environ.get(
            f"ODOO_QUEUE_JOB_JOBRUNNER_DB_{p.upper()}"
        ) or queue_job_config.get("jobrunner_db_" + p)

        if cfg:
            connection_info[p] = cfg

    return connection_info


def _async_http_get(scheme, host, port, user, password, db_name, job_uuid):
    # TODO: better way to HTTP GET asynchronously (grequest, ...)?
    #       if this was python3 I would be doing this with
    #       asyncio, aiohttp and aiopg
    def urlopen():
        url = f"{scheme}://{host}:{port}/queue_job/runjob?db={db_name}&job_uuid={job_uuid}"
        # pylint: disable=except-pass
        try:
            auth = None
            if user:
                auth = (user, password)
            # we are not interested in the result, so we set a short timeout
            # but not too short so we trap and log hard configuration errors
            response = requests.get(url, timeout=1, auth=auth)

            # raise_for_status will result in either nothing, a Client Error
            # for HTTP Response codes between 400 and 500 or a Server Error
            # for codes between 500 and 600
            response.raise_for_status()
        except requests.Timeout:
            # A timeout is a normal behaviour, it shouldn't be logged as an exception
            pass
        except Exception:
            _logger.exception("exception in GET %s", url)

    thread = threading.Thread(target=urlopen)
    thread.daemon = True
    thread.start()


class Database:
    def __init__(self, db_name):
        self.db_name = db_name
        connection_info = _connection_info_for(db_name)
        self.conn = psycopg2.connect(**connection_info)
        try:
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            self.has_queue_job = self._has_queue_job()
            if self.has_queue_job:
                self._acquire_master_lock()
                self._initialize()
        except BaseException:
            self.close()
            raise

    def close(self):
        # pylint: disable=except-pass
        # if close fail for any reason, it's either because it's already closed
        # and we don't care, or for any reason but anyway it will be closed on
        # del
        try:
            self.conn.close()
        except Exception:
            pass
        self.conn = None

    def _acquire_master_lock(self):
        """Acquire the master runner lock or raise MasterElectionLost"""
        with closing(self.conn.cursor()) as cr:
            cr.execute("SELECT pg_try_advisory_lock(%s)", (PG_ADVISORY_LOCK_ID,))
            if not cr.fetchone()[0]:
                msg = f"could not acquire master runner lock on {self.db_name}"
                raise MasterElectionLost(msg)

    def _has_queue_job(self):
        with closing(self.conn.cursor()) as cr:
            cr.execute(
                "SELECT 1 FROM pg_tables WHERE tablename=%s", ("ir_module_module",)
            )
            if not cr.fetchone():
                _logger.debug("%s doesn't seem to be an odoo db", self.db_name)
                return False
            cr.execute(
                "SELECT 1 FROM ir_module_module WHERE name=%s AND state=%s",
                ("queue_job", "installed"),
            )
            if not cr.fetchone():
                _logger.debug("queue_job is not installed for db %s", self.db_name)
                return False
            cr.execute(
                """SELECT COUNT(1)
                FROM information_schema.triggers
                WHERE event_object_table = %s
                AND trigger_name = %s""",
                ("queue_job", "queue_job_notify"),
            )
            if cr.fetchone()[0] != 3:  # INSERT, DELETE, UPDATE
                _logger.error(
                    "queue_job_notify trigger is missing in db %s", self.db_name
                )
                return False
            return True

    def _initialize(self):
        with closing(self.conn.cursor()) as cr:
            cr.execute("LISTEN queue_job")

    def load_channels_config(self):
        """Return the channels configuration stored in the database"""
        with closing(self.conn.cursor()) as cr:
            cr.execute(
                "SELECT complete_name, "
                "COALESCE(capacity, 0), "
                "COALESCE(sequential, false), "
                "COALESCE(throttle, 0), "
                "COALESCE(paused, false) "
                "FROM queue_job_channel "
            )
            rows = cr.fetchall()
            configs = [
                ChannelConfig(
                    name=name,
                    capacity=capacity,
                    sequential=sequential,
                    throttle=throttle,
                    paused=paused,
                )
                for name, capacity, sequential, throttle, paused in rows
            ]
            return configs

    @contextmanager
    def select_jobs(self, where, args):
        # pylint: disable=sql-injection
        # the checker thinks we are injecting values but we are not, we are
        # adding the where conditions, values are added later properly with
        # parameters
        query = (
            "SELECT channel, uuid, id as seq, date_created, "
            "priority, EXTRACT(EPOCH FROM eta), state "
            f"FROM queue_job WHERE {where}"
        )
        with closing(self.conn.cursor("select_jobs", withhold=True)) as cr:
            cr.execute(query, args)
            yield cr

    def keep_alive(self):
        query = "SELECT 1"
        with closing(self.conn.cursor()) as cr:
            cr.execute(query)

    def set_job_enqueued(self, uuid):
        with closing(self.conn.cursor()) as cr:
            cr.execute(
                "UPDATE queue_job SET state=%s, "
                "date_enqueued=date_trunc('seconds', "
                "                         now() at time zone 'utc') "
                "WHERE uuid=%s",
                (ENQUEUED, uuid),
            )

    def _query_requeue_dead_jobs(self):
        return """
            UPDATE
                queue_job
            SET
                state=(
                    CASE
                        WHEN
                            max_retries IS NOT NULL AND
                            max_retries != 0 AND -- infinite retries if max_retries is 0
                            retry IS NOT NULL AND
                            retry>max_retries
                        THEN 'failed'
                        ELSE 'pending'
                    END),
                retry=(
                    CASE
                        WHEN state='started'
                        THEN COALESCE(retry,0)+1 ELSE retry
                    END),
                exc_name=(
                    CASE
                        WHEN
                            max_retries IS NOT NULL AND
                            max_retries != 0 AND -- infinite retries if max_retries is 0
                            retry IS NOT NULL AND
                            retry>max_retries
                        THEN 'JobFoundDead'
                        ELSE exc_name
                    END),
                exc_info=(
                    CASE
                        WHEN
                            max_retries IS NOT NULL AND
                            max_retries != 0 AND -- infinite retries if max_retries is 0
                            retry IS NOT NULL AND
                            retry>max_retries
                        THEN 'Job found dead after too many retries'
                        ELSE exc_info
                    END)
            WHERE
                state IN ('enqueued','started')
                AND date_enqueued < (now() AT TIME ZONE 'utc' - INTERVAL '10 sec')
                AND (
                    id in (
                        SELECT
                            queue_job_id
                        FROM
                            queue_job_lock
                        WHERE
                            queue_job_lock.queue_job_id = queue_job.id
                        FOR NO KEY UPDATE SKIP LOCKED
                    )
                    OR NOT EXISTS (
                        SELECT
                            1
                        FROM
                            queue_job_lock
                        WHERE
                            queue_job_lock.queue_job_id = queue_job.id
                    )
                )
            RETURNING uuid
            """

    def requeue_dead_jobs(self):
        """
        Set started and enqueued jobs but not locked to pending

        A job is locked when it's being executed
        When a job is killed, it releases the lock

        If the number of retries exceeds the number of max retries,
        the job is set as 'failed' with the error 'JobFoundDead'.

        Adding a buffer on 'date_enqueued' to check
        that it has been enqueued for more than 10sec.
        This prevents from requeuing jobs before they are actually started.

        When Odoo shuts down normally, it waits for running jobs to finish.
        However, when the Odoo server crashes or is otherwise force-stopped,
        running jobs are interrupted while the runner has no chance to know
        they have been aborted.

        This also handles orphaned jobs (enqueued but never started, no lock).
        This edge case occurs when the runner marks a job as 'enqueued'
        but the HTTP request to start the job never reaches the Odoo server
        (e.g., due to server shutdown/crash between setting enqueued and
        the controller receiving the request).
        """

        with closing(self.conn.cursor()) as cr:
            query = self._query_requeue_dead_jobs()

            cr.execute(query)

            for (uuid,) in cr.fetchall():
                _logger.warning("Re-queued dead job with uuid: %s", uuid)


class QueueJobRunner:
    def __init__(
        self,
        scheme="http",
        host="localhost",
        port=8069,
        user=None,
        password=None,
        channel_config_string=None,
    ):
        self.scheme = scheme
        self.host = host
        self.port = port
        self.user = user
        self.password = password

        if channel_config_string is None:
            channel_config_string = _channels()

        self._server_side_channel_manager = None
        if _server_side_channels_configured():
            channel_manager = ChannelManager()
            channel_manager.simple_configure(channel_config_string)
            self._server_side_channel_manager = channel_manager

        self.max_capacity = _max_capacity()

        self.channel_manager_by_db = {}

        self.db_by_name = {}
        self._stop = False
        self._stop_pipe = os.pipe()

    def __del__(self):
        # pylint: disable=except-pass
        try:
            os.close(self._stop_pipe[0])
        except OSError:
            pass
        try:
            os.close(self._stop_pipe[1])
        except OSError:
            pass

    @classmethod
    def from_environ_or_config(cls):
        scheme = os.environ.get("ODOO_QUEUE_JOB_SCHEME") or queue_job_config.get(
            "scheme"
        )
        host = (
            os.environ.get("ODOO_QUEUE_JOB_HOST")
            or queue_job_config.get("host")
            or config["http_interface"]
        )
        port = (
            os.environ.get("ODOO_QUEUE_JOB_PORT")
            or queue_job_config.get("port")
            or config["http_port"]
        )
        user = os.environ.get("ODOO_QUEUE_JOB_HTTP_AUTH_USER") or queue_job_config.get(
            "http_auth_user"
        )
        password = os.environ.get(
            "ODOO_QUEUE_JOB_HTTP_AUTH_PASSWORD"
        ) or queue_job_config.get("http_auth_password")
        runner = cls(
            scheme=scheme or "http",
            host=host or "localhost",
            port=port or 8069,
            user=user,
            password=password,
        )
        return runner

    def get_db_names(self):
        if config["db_name"]:
            db_names = config["db_name"].split(",")
        else:
            db_names = odoo.service.db.list_dbs(True)
        return db_names

    def close_databases(self, remove_jobs=True):
        for db_name, db in self.db_by_name.items():
            try:
                if remove_jobs:
                    self.channel_manager_by_db[db_name].remove_db(db_name)
                db.close()
            except Exception:
                _logger.warning("error closing database %s", db_name, exc_info=True)
        self.db_by_name = {}

    def _build_channel_manager(self, db):
        """Build and configure the channel manager of a database"""
        # TODO: parse string "capacity per database with pattern"
        db_max = _db_max_capacity()
        channels_config = db.load_channels_config()
        channel_manager = ChannelManager()

        root_config = next(
            (config for config in channels_config if config.name == "root"), None
        )
        if root_config is None:
            root_config = ChannelConfig("root")
            channels_config.insert(0, root_config)

        if not db_max:
            # if a database is set at 0, it does not run any jobs, pause it
            root_config.paused = True
        elif not root_config.capacity:
            root_config.capacity = db_max
        else:
            root_config.capacity = min(root_config.capacity, db_max)
        channel_manager.configure(channels_config)
        return channel_manager

    def _reconfigure_db(self, db_name):
        """Rebuild the channel manager for a database and reload its jobs"""
        db = self.db_by_name.get(db_name)
        if db is None:
            return
        if self._server_side_channel_manager:
            # fallback on server-side configuration with a unique channel manager
            channel_manager = self._server_side_channel_manager
        else:
            channel_manager = self._build_channel_manager(db)
        with db.select_jobs("state in %s", (NOT_DONE,)) as cr:
            for job_data in cr:
                channel_manager.notify(db_name, *job_data)
        self.channel_manager_by_db[db_name] = channel_manager
        _logger.info("channels configuration loaded for db %s", db_name)

    def initialize_databases(self):
        for db_name in sorted(self.get_db_names()):
            # sorting is important to avoid deadlocks in acquiring the master lock
            db = Database(db_name)
            if db.has_queue_job:
                self.db_by_name[db_name] = db
                self._reconfigure_db(db_name)
                _logger.info("queue job runner ready for db %s", db_name)
            else:
                db.close()

    def requeue_dead_jobs(self):
        for db in self.db_by_name.values():
            if db.has_queue_job:
                db.requeue_dead_jobs()

    def _dispatch_job(self, job):
        _logger.info("asking Odoo to run job %s on db %s", job.uuid, job.db_name)
        self.db_by_name[job.db_name].set_job_enqueued(job.uuid)
        _async_http_get(
            self.scheme,
            self.host,
            self.port,
            self.user,
            self.password,
            job.db_name,
            job.uuid,
        )

    def run_jobs(self):
        db_names = list(self.channel_manager_by_db)
        if not db_names:
            return

        now = _odoo_now()

        # TODO: round robin
        for db_name in db_names:
            jobs = self.channel_manager_by_db[db_name].get_jobs_to_run(now)
            while True:
                if self._stop:
                    break
                # TODO: check if max capacity for db reached so another db
                # can dispatch jobs
                job = next(jobs, None)
                if job is None:
                    break
                self._dispatch_job(job)

    def process_notifications(self):
        reload_db_names = set()
        for db in self.db_by_name.values():
            if not db.conn.notifies:
                # If there are no activity in the queue_job table it seems that
                # tcp keepalives are not sent (in that very specific scenario),
                # causing some intermediaries (such as haproxy) to close the
                # connection, making the jobrunner to restart on a socket error
                db.keep_alive()
            while db.conn.notifies:
                if self._stop:
                    break
                notification = db.conn.notifies.pop()
                payload = notification.payload
                if payload == RELOAD_PAYLOAD and not self._server_side_channel_manager:
                    reload_db_names.add(db.db_name)
                    continue

                uuid = payload
                channel_manager = self.channel_manager_by_db[db.db_name]
                with db.select_jobs("uuid = %s", (uuid,)) as cr:
                    job_datas = cr.fetchone()
                    if job_datas:
                        channel_manager.notify(db.db_name, *job_datas)
                    else:
                        channel_manager.remove_job(uuid)

        for db_name in reload_db_names:
            self._reconfigure_db(db_name)

    def next_wakeup_time(self):
        wakeup_times = [
            channel_manager.get_wakeup_time()
            for channel_manager in self.channel_manager_by_db.values()
        ]
        return min(wakeup_times, default=0)

    def wait_notification(self):
        for db in self.db_by_name.values():
            if db.conn.notifies:
                # something is going on in the queue, no need to wait
                return
        # wait for something to happen in the queue_job tables
        # we'll select() on database connections and the stop pipe
        conns = [db.conn for db in self.db_by_name.values()]
        conns.append(self._stop_pipe[0])
        # look if the channels specify a wakeup time
        # TODO: get min wakeup time?
        wakeup_time = self.next_wakeup_time()
        if not wakeup_time:
            # this could very well be no timeout at all, because
            # any activity in the job queue will wake us up, but
            # let's have a timeout anyway, just to be safe
            timeout = SELECT_TIMEOUT
        else:
            timeout = wakeup_time - _odoo_now()
        # wait for a notification or a timeout;
        # if timeout is negative (ie wakeup time in the past),
        # do not wait; this should rarely happen
        # because of how get_wakeup_time is designed; actually
        # if timeout remains a large negative number, it is most
        # probably a bug
        _logger.debug("select() timeout: %.2f sec", timeout)
        if timeout > 0:
            if conns and not self._stop:
                with select() as sel:
                    for conn in conns:
                        sel.register(conn, selectors.EVENT_READ)
                    events = sel.select(timeout=timeout)
                    for key, _mask in events:
                        if key.fileobj == self._stop_pipe[0]:
                            # stop-pipe is not a conn so doesn't need poll()
                            continue
                        key.fileobj.poll()

    def stop(self):
        _logger.info("graceful stop requested")
        self._stop = True
        # wakeup the select() in wait_notification
        os.write(self._stop_pipe[1], b".")

    def run(self):
        _logger.info("starting")
        while not self._stop:
            # outer loop does exception recovery
            try:
                _logger.debug("initializing database connections")
                # TODO: how to detect new databases or databases
                #       on which queue_job is installed after server start?
                self.initialize_databases()
                _logger.info("database connections ready")
                # inner loop does the normal processing
                while not self._stop:
                    self.requeue_dead_jobs()
                    self.process_notifications()
                    self.run_jobs()
                    self.wait_notification()
            except KeyboardInterrupt:
                self.stop()
            except InterruptedError:
                # Interrupted system call, i.e. KeyboardInterrupt during select
                self.stop()
            except MasterElectionLost as e:
                _logger.debug(
                    "master election lost: %s, sleeping %ds and retrying",
                    e,
                    ERROR_RECOVERY_DELAY,
                )
                self.close_databases()
                time.sleep(ERROR_RECOVERY_DELAY)
            except Exception:
                _logger.exception(
                    "exception: sleeping %ds and retrying", ERROR_RECOVERY_DELAY
                )
                self.close_databases()
                time.sleep(ERROR_RECOVERY_DELAY)
        self.close_databases(remove_jobs=False)
        _logger.info("stopped")
