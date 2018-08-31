# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
from threading import Thread
import time

from odoo.service import server
from odoo.tools import config

from .runner import QueueJobRunner

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
    """ Jobrunner workers """

    def __init__(self, multi):
        super(WorkerJobRunner, self).__init__(multi)
        self.watchdog_timeout = None
        self.runner = QueueJobRunner.from_environ_or_config()

    def sleep(self):
        pass

    def signal_handler(self, sig, frame):
        _logger.debug("WorkerJobRunner (%s) received signal %s", self.pid, sig)
        super(WorkerJobRunner, self).signal_handler(sig, frame)
        self.runner.stop()

    def process_work(self):
        _logger.debug("WorkerJobRunner (%s) starting up", self.pid)
        time.sleep(START_DELAY)
        self.runner.run()


runner_thread = None

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
    if not server.jobrunner:
        server.worker_spawn(WorkerJobRunner, server.jobrunner)


def prefork_worker_pop(server, pid):
    res = orig_prefork_worker_pop(server, pid)
    if pid in server.jobrunner:
        server.jobrunner.pop(pid)
    return res


def threaded_start(server, *args, **kwargs):
    global runner_thread
    res = orig_threaded_start(server, *args, **kwargs)
    if not config['stop_after_init']:
        _logger.info("starting jobrunner thread (in threaded server)")
        runner_thread = QueueJobRunnerThread()
        runner_thread.start()
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
