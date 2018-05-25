# Copyright 2015-2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import doctest
# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
from odoo.addons.queue_job.jobrunner import runner


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(runner))
    return tests
