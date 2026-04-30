# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
import doctest

from odoo.tests import BaseCase, tagged

# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
from odoo.addons.queue_job.jobrunner import channels


@tagged("doctest")
class TestDoctest(BaseCase):
    def test_doctest(self):
        doctest.testmod(channels, exclude_empty=True, raise_on_error=True)
