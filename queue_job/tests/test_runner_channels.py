# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import doctest
# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
from odoo.addons.queue_job.jobrunner import channels


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(channels))
    return tests
