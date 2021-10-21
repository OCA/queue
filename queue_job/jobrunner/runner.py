# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2015-2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
"""
What is the job runner?
-----------------------
The job runner is the main process managing the dispatch of delayed jobs to
available Odoo workers

How does it work?
-----------------

* It starts as a thread in the Odoo main process
* It receives postgres NOTIFY messages each time jobs are
  added or updated in the queue_job table.
* It maintains an in-memory priority queue of jobs that
  is populated from the queue_job tables in all databases.
* It does not run jobs itself, but asks Odoo to run them through an
  anonymous ``/queue_job/runjob`` HTTP request. [1]_

How to use it?
--------------

* Optionally adjust your configuration through environment variables:

  - ``ODOO_QUEUE_JOB_CHANNELS=root:4`` (or any other channels
    configuration), default ``root:1``.
  - ``ODOO_QUEUE_JOB_SCHEME=https``, default ``http``.
  - ``ODOO_QUEUE_JOB_HOST=load-balancer``, default ``http_interface``
    or ``localhost`` if unset.
  - ``ODOO_QUEUE_JOB_PORT=443``, default ``http_port`` or 8069 if unset.
  - ``ODOO_QUEUE_JOB_HTTP_AUTH_USER=jobrunner``, default empty.
  - ``ODOO_QUEUE_JOB_HTTP_AUTH_PASSWORD=s3cr3t``, default empty.
  - ``ODOO_QUEUE_JOB_JOBRUNNER_DB_HOST=master-db``, default ``db_host``
    or ``False`` if unset.
  - ``ODOO_QUEUE_JOB_JOBRUNNER_DB_PORT=5432``, default ``db_port``
    or ``False`` if unset.

* Alternatively, configure the channels through the Odoo configuration
  file, like:

.. code-block:: ini

  [queue_job]
  channels = root:4
  scheme = https
  host = load-balancer
  port = 443
  http_auth_user = jobrunner
  http_auth_password = s3cr3t
  jobrunner_db_host = master-db
  jobrunner_db_port = 5432

* Or, if using ``anybox.recipe.odoo``, add this to your buildout configuration:

.. code-block:: ini

  [odoo]
  recipe = anybox.recipe.odoo
  (...)
  queue_job.channels = root:4
  queue_job.scheme = https
  queue_job.host = load-balancer
  queue_job.port = 443
  queue_job.http_auth_user = jobrunner
  queue_job.http_auth_password = s3cr3t

* Start Odoo with ``--load=web,web_kanban,queue_job``
  and ``--workers`` greater than 1 [2]_, or set the ``server_wide_modules``
  option in The Odoo configuration file:

.. code-block:: ini

  [options]
  (...)
  workers = 4
  server_wide_modules = web,web_kanban,queue_job
  (...)

* Or, if using ``anybox.recipe.odoo``:

.. code-block:: ini

  [odoo]
  recipe = anybox.recipe.odoo
  (...)
  options.workers = 4
  options.server_wide_modules = web,web_kanban,queue_job

* Confirm the runner is starting correctly by checking the odoo log file:

.. code-block:: none

  ...INFO...queue_job.jobrunner.runner: starting
  ...INFO...queue_job.jobrunner.runner: initializing database connections
  ...INFO...queue_job.jobrunner.runner: queue job runner ready for db <dbname>
  ...INFO...queue_job.jobrunner.runner: database connections ready

* Create jobs (eg using base_import_async) and observe they
  start immediately and in parallel.

* Tip: to enable debug logging for the queue job, use
  ``--log-handler=odoo.addons.queue_job:DEBUG``

Caveat
------

* After creating a new database or installing queue_job on an
  existing database, Odoo must be restarted for the runner to detect it.

* When Odoo shuts down normally, it waits for running jobs to finish.
  However, when the Odoo server crashes or is otherwise force-stopped,
  running jobs are interrupted while the runner has no chance to know
  they have been aborted. In such situations, jobs may remain in
  ``started`` or ``enqueued`` state after the Odoo server is halted.
  Since the runner has no way to know if they are actually running or
  not, and does not know for sure if it is safe to restart the jobs,
  it does not attempt to restart them automatically. Such stale jobs
  therefore fill the running queue and prevent other jobs to start.
  You must therefore requeue them manually, either from the Jobs view,
  or by running the following SQL statement *before starting Odoo*:

.. code-block:: sql

  update queue_job set state='pending' where state in ('started', 'enqueued')

.. rubric:: Footnotes

.. [1] From a security standpoint, it is safe to have an anonymous HTTP
       request because this request only accepts to run jobs that are
       enqueued.
.. [2] It works with the threaded Odoo server too, although this way
       of running Odoo is obviously not for production purposes.
"""

from contextlib import closing
import datetime
import logging
import os
import select
import threading
import time

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import requests

import odoo
from odoo.tools import config

from .channels import ChannelManager, PENDING, ENQUEUED, NOT_DONE

SELECT_TIMEOUT = 60
ERROR_RECOVERY_DELAY = 5

_logger = logging.getLogger(__name__)


session = requests.Session()


# Unfortunately, it is not possible to extend the Odoo
# server command line arguments, so we resort to environment variables
# to configure the runner (channels mostly).
#
# On the other hand, the odoo configuration file can be extended at will,
# so we check it in addition to the environment variables.


def _channels():
    return (
        os.environ.get('ODOO_QUEUE_JOB_CHANNELS') or
        config.misc.get("queue_job", {}).get("channels") or
        "root:1"
    )


def _datetime_to_epoch(dt):
    # important: this must return the same as postgresql
    # EXTRACT(EPOCH FROM TIMESTAMP dt)
    return (dt - datetime.datetime(1970, 1, 1)).total_seconds()


def _odoo_now():
    dt = datetime.datetime.utcnow()
    return _datetime_to_epoch(dt)


def _connection_info_for(db_name):
    db_or_uri, connection_info = odoo.sql_db.connection_info_for(db_name)

    for p in ('host', 'port'):
        cfg = (os.environ.get('ODOO_QUEUE_JOB_JOBRUNNER_DB_%s' % p.upper()) or
               config.misc
               .get("queue_job", {}).get('jobrunner_db_' + p))

        if cfg:
            connection_info[p] = cfg

    return connection_info


session = requests.Session()


def _async_http_get(scheme, host, port, user, password, db_name, job_uuid):
    if not session.cookies:
        # obtain an anonymous session
        _logger.info("obtaining an anonymous session for the job runner")
        url = ('%s://%s:%s/queue_job/session' % (scheme, host, port))
        auth = None
        if user:
            auth = (user, password)
        response = session.get(url, timeout=30, auth=auth)
        response.raise_for_status()

    # Method to set failed job (due to timeout, etc) as pending,
    # to avoid keeping it as enqueued.
    def set_job_pending():
        connection_info = _connection_info_for(db_name)
        conn = psycopg2.connect(**connection_info)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with closing(conn.cursor()) as cr:
            cr.execute(
                "UPDATE queue_job SET state=%s, "
                "date_enqueued=NULL, date_started=NULL "
                "WHERE uuid=%s and state=%s "
                "RETURNING uuid", (PENDING, job_uuid, ENQUEUED)
            )
            if cr.fetchone():
                _logger.warning(
                    "state of job %s was reset from %s to %s",
                    job_uuid, ENQUEUED, PENDING,
                )

    # TODO: better way to HTTP GET asynchronously (grequest, ...)?
    #       if this was python3 I would be doing this with
    #       asyncio, aiohttp and aiopg
    def urlopen():
        url = ('%s://%s:%s/queue_job/runjob?db=%s&job_uuid=%s' %
               (scheme, host, port, db_name, job_uuid))
        try:
            auth = None
            if user:
                auth = (user, password)
            # we are not interested in the result, so we set a short timeout
            # but not too short so we trap and log hard configuration errors
            response = session.get(url, timeout=1, auth=auth)

            # raise_for_status will result in either nothing, a Client Error
            # for HTTP Response codes between 400 and 500 or a Server Error
            # for codes between 500 and 600
            response.raise_for_status()
        except requests.Timeout:
            set_job_pending()
        except Exception:
            _logger.exception("exception in GET %s", url)
            session.cookies.clear()
            set_job_pending()
    thread = threading.Thread(target=urlopen)
    thread.daemon = True
    thread.start()


class Database(object):

    def __init__(self, db_name):
        self.db_name = db_name
        connection_info = _connection_info_for(db_name)
        self.conn = psycopg2.connect(**connection_info)
        self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        self.has_queue_job = self._has_queue_job()
        if self.has_queue_job:
            self._initialize()

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

    def _has_queue_job(self):
        with closing(self.conn.cursor()) as cr:
            cr.execute("SELECT 1 FROM pg_tables WHERE tablename=%s",
                       ('ir_module_module',))
            if not cr.fetchone():
                return False
            cr.execute(
                "SELECT 1 FROM ir_module_module WHERE name=%s AND state=%s",
                ('queue_job', 'installed')
            )
            return cr.fetchone()

    def _initialize(self):
        with closing(self.conn.cursor()) as cr:
            # this is the trigger that sends notifications when jobs change
            cr.execute("""
                DROP TRIGGER IF EXISTS queue_job_notify ON queue_job;

                CREATE OR REPLACE
                    FUNCTION queue_job_notify() RETURNS trigger AS $$
                BEGIN
                    IF TG_OP = 'DELETE' THEN
                        IF OLD.state != 'done' THEN
                            PERFORM pg_notify('queue_job', OLD.uuid);
                        END IF;
                    ELSE
                        PERFORM pg_notify('queue_job', NEW.uuid);
                    END IF;
                    RETURN NULL;
                END;
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER queue_job_notify
                    AFTER INSERT OR UPDATE OR DELETE
                    ON queue_job
                    FOR EACH ROW EXECUTE PROCEDURE queue_job_notify();
            """)
            cr.execute("LISTEN queue_job")

    def select_jobs(self, where, args):
        # pylint: disable=sql-injection
        # the checker thinks we are injecting values but we are not, we are
        # adding the where conditions, values are added later properly with
        # parameters
        query = ("SELECT channel, uuid, id as seq, date_created, "
                 "priority, EXTRACT(EPOCH FROM eta), state "
                 "FROM queue_job WHERE %s" %
                 (where, ))
        with closing(self.conn.cursor()) as cr:
            cr.execute(query, args)
            return list(cr.fetchall())

    def set_job_enqueued(self, uuid):
        with closing(self.conn.cursor()) as cr:
            cr.execute("UPDATE queue_job SET state=%s, "
                       "date_enqueued=date_trunc('seconds', "
                       "                         now() at time zone 'utc') "
                       "WHERE uuid=%s",
                       (ENQUEUED, uuid))


class QueueJobRunner(object):

    def __init__(self,
                 scheme='http',
                 host='localhost',
                 port=8069,
                 user=None,
                 password=None,
                 channel_config_string=None):
        self.scheme = scheme
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.channel_manager = ChannelManager()
        if channel_config_string is None:
            channel_config_string = _channels()
        self.channel_manager.simple_configure(channel_config_string)
        self.db_by_name = {}
        self._stop = False
        self._stop_pipe = os.pipe()

    def get_db_names(self):
        if odoo.tools.config['db_name']:
            db_names = odoo.tools.config['db_name'].split(',')
        else:
            db_names = odoo.service.db.exp_list(True)
        return db_names

    def close_databases(self, remove_jobs=True):
        for db_name, db in self.db_by_name.items():
            try:
                if remove_jobs:
                    self.channel_manager.remove_db(db_name)
                db.close()
            except Exception:
                _logger.warning('error closing database %s',
                                db_name, exc_info=True)
        self.db_by_name = {}

    def initialize_databases(self):
        for db_name in self.get_db_names():
            db = Database(db_name)
            if not db.has_queue_job:
                _logger.debug('queue_job is not installed for db %s', db_name)
            else:
                self.db_by_name[db_name] = db
                for job_data in db.select_jobs('state in %s', (NOT_DONE,)):
                    self.channel_manager.notify(db_name, *job_data)
                _logger.info('queue job runner ready for db %s', db_name)

    def run_jobs(self):
        now = _odoo_now()
        for job in self.channel_manager.get_jobs_to_run(now):
            if self._stop:
                break
            _logger.info("asking Odoo to run job %s on db %s",
                         job.uuid, job.db_name)
            self.db_by_name[job.db_name].set_job_enqueued(job.uuid)
            _async_http_get(self.scheme,
                            self.host,
                            self.port,
                            self.user,
                            self.password,
                            job.db_name,
                            job.uuid)

    def process_notifications(self):
        for db in self.db_by_name.values():
            while db.conn.notifies:
                if self._stop:
                    break
                notification = db.conn.notifies.pop()
                uuid = notification.payload
                job_datas = db.select_jobs('uuid = %s', (uuid,))
                if job_datas:
                    self.channel_manager.notify(db.db_name, *job_datas[0])
                else:
                    self.channel_manager.remove_job(uuid)

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
        wakeup_time = self.channel_manager.get_wakeup_time()
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
            conns, _, _ = select.select(conns, [], [], timeout)
            if conns and not self._stop:
                for conn in conns:
                    conn.poll()

    def stop(self):
        _logger.info("graceful stop requested")
        self._stop = True
        # wakeup the select() in wait_notification
        os.write(self._stop_pipe[1], b'.')

    def run(self):
        _logger.info("starting")
        while not self._stop:
            # outer loop does exception recovery
            try:
                _logger.info("initializing database connections")
                # TODO: how to detect new databases or databases
                #       on which queue_job is installed after server start?
                self.initialize_databases()
                _logger.info("database connections ready")
                # inner loop does the normal processing
                while not self._stop:
                    self.process_notifications()
                    self.run_jobs()
                    self.wait_notification()
            except KeyboardInterrupt:
                self.stop()
            except Exception:
                _logger.exception("exception: sleeping %ds and retrying",
                                  ERROR_RECOVERY_DELAY)
                self.close_databases()
                time.sleep(ERROR_RECOVERY_DELAY)
        self.close_databases(remove_jobs=False)
        _logger.info("stopped")
