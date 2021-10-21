# -*- coding: utf-8 -*-
# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os
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
        port = os.environ.get('ODOO_CONNECTOR_PORT') or config['xmlrpc_port']
        self.runner = QueueJobRunner(port or 8069)

    def run(self):
        # sleep a bit to let the workers start at ease
        time.sleep(START_DELAY)
        self.runner.run()

    def stop(self):
        self.runner.stop()


runner_thread = None

orig_prefork_start = server.PreforkServer.start
orig_prefork_stop = server.PreforkServer.stop
orig_threaded_start = server.ThreadedServer.start
orig_threaded_stop = server.ThreadedServer.stop


def prefork_start(server, *args, **kwargs):
    global runner_thread
    res = orig_prefork_start(server, *args, **kwargs)
    if not config['stop_after_init']:
        _logger.info("starting jobrunner thread (in prefork server)")
        runner_thread = QueueJobRunnerThread()
        runner_thread.start()
    return res


def prefork_stop(server, graceful=True):
    global runner_thread
    if runner_thread:
        runner_thread.stop()
    res = orig_prefork_stop(server, graceful)
    if runner_thread:
        runner_thread.join()
        runner_thread = None
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


server.PreforkServer.start = prefork_start
server.PreforkServer.stop = prefork_stop
server.ThreadedServer.start = threaded_start
server.ThreadedServer.stop = threaded_stop
