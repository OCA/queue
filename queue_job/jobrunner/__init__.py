# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
from threading import Thread
import time

from odoo.service import server
from odoo.tools import config

try:
    # Preferred source when available: structured [queue_job] section provided
    # by OCA's server_environment addon.
    from odoo.addons.server_environment import serv_config

    if serv_config.has_section("queue_job"):
        queue_job_config = serv_config["queue_job"]
    else:
        queue_job_config = {}
except ImportError:
    # Odoo 19: config.misc is no longer available. Build a minimal config
    # from flat odoo.conf options so the runner works without server_environment.
    queue_job_config = {}

# Merge flat odoo.conf options as a fallback (applies regardless of whether
# server_environment is installed). Precedence is enforced later where used:
# - Environment variables (highest) are read directly in runner functions
# - Then values coming from server_environment's [queue_job] section (above)
# - Finally flat odoo.conf options below (lowest)
#
# Supported flat options (under the [options] section in odoo.conf):
#   queue_job_channels = root:2,mychan:1
#   queue_job_jobrunner_db_host = localhost
#   queue_job_jobrunner_db_port = 5432
#   queue_job_jobrunner_db_user = odoo_queue
#   queue_job_jobrunner_db_password = odoo_queue
_flat = {}
channels = config.get("queue_job_channels")
if channels:
    _flat["channels"] = channels
for p in ("host", "port", "user", "password"):
    v = config.get(f"queue_job_jobrunner_db_{p}")
    if v:
        _flat[f"jobrunner_db_{p}"] = v

# Do not override keys coming from server_environment if present
for k, v in _flat.items():
    queue_job_config.setdefault(k, v)


from .runner import QueueJobRunner, _channels

_logger = logging.getLogger(__name__)

START_DELAY = 5


# Here we monkey patch the Odoo server to start the job runner thread
# in the main server process (and not in forked workers). This is
# very easy to deploy as we don't need another startup script.


class QueueJobRunnerThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.runner = QueueJobRunner.from_environ_or_config()

    def run(self):
        # sleep a bit to let the workers start at ease
        time.sleep(START_DELAY)
        self.runner.run()

    def stop(self):
        self.runner.stop()


class WorkerJobRunner(server.Worker):
    """Jobrunner workers"""

    def __init__(self, multi):
        super().__init__(multi)
        self.watchdog_timeout = None
        self.runner = QueueJobRunner.from_environ_or_config()
        self._recover = False

    def sleep(self):
        pass

    def signal_handler(self, sig, frame):  # pylint: disable=missing-return
        _logger.debug("WorkerJobRunner (%s) received signal %s", self.pid, sig)
        super().signal_handler(sig, frame)
        self.runner.stop()

    def process_work(self):
        if self._recover:
            _logger.info("WorkerJobRunner (%s) runner is reinitialized", self.pid)
            self.runner = QueueJobRunner.from_environ_or_config()
            self._recover = False
        _logger.debug("WorkerJobRunner (%s) starting up", self.pid)
        time.sleep(START_DELAY)
        self.runner.run()

    def signal_time_expired_handler(self, n, stack):
        _logger.info(
            "Worker (%d) CPU time limit (%s) reached.Stop gracefully and recover",
            self.pid,
            config["limit_time_cpu"],
        )
        self._recover = True
        self.runner.stop()


runner_thread = None


def _is_runner_enabled():
    return not _channels().strip().startswith("root:0")


def _start_runner_thread(server_type):
    global runner_thread
    if not config["stop_after_init"]:
        if _is_runner_enabled():
            _logger.info("starting jobrunner thread (in %s)", server_type)
            runner_thread = QueueJobRunnerThread()
            runner_thread.start()
        else:
            _logger.info(
                "jobrunner thread (in %s) NOT started, "
                "because the root channel's capacity is set to 0",
                server_type,
            )


orig_prefork__init__ = server.PreforkServer.__init__
orig_prefork_process_spawn = server.PreforkServer.process_spawn
orig_prefork_worker_pop = server.PreforkServer.worker_pop
orig_threaded_start = server.ThreadedServer.start
orig_threaded_stop = server.ThreadedServer.stop


def prefork__init__(server, app):
    res = orig_prefork__init__(server, app)
    server.jobrunner = {}
    return res


def prefork_process_spawn(server):
    orig_prefork_process_spawn(server)
    if not hasattr(server, "jobrunner"):
        # if 'queue_job' is not in server wide modules, PreforkServer is
        # not initialized with a 'jobrunner' attribute, skip this
        return
    if not server.jobrunner and _is_runner_enabled():
        server.worker_spawn(WorkerJobRunner, server.jobrunner)


def prefork_worker_pop(server, pid):
    res = orig_prefork_worker_pop(server, pid)
    if not hasattr(server, "jobrunner"):
        # if 'queue_job' is not in server wide modules, PreforkServer is
        # not initialized with a 'jobrunner' attribute, skip this
        return res
    if pid in server.jobrunner:
        server.jobrunner.pop(pid)
    return res


def threaded_start(server, *args, **kwargs):
    res = orig_threaded_start(server, *args, **kwargs)
    _start_runner_thread("threaded server")
    return res


def threaded_stop(server):
    global runner_thread
    if runner_thread:
        runner_thread.stop()
    res = orig_threaded_stop(server)
    if runner_thread:
        runner_thread.join()
        runner_thread = None
    return res


server.PreforkServer.__init__ = prefork__init__
server.PreforkServer.process_spawn = prefork_process_spawn
server.PreforkServer.worker_pop = prefork_worker_pop
server.ThreadedServer.start = threaded_start
server.ThreadedServer.stop = threaded_stop
