# -*- coding: utf-8 -*-
# Copyright 2015-2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import doctest
from odoo.addons.queue_job.jobrunner import channels


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(channels))
    return tests
