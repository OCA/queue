# -*- coding: utf-8 -*-
# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import doctest
from odoo.addons.queue_job.jobrunner import channels


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(channels))
    return tests
