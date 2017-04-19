# -*- coding: utf-8 -*-
# copyright 2016 Camptocamp
# license agpl-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from datetime import datetime, date
import json

from odoo.tests import common
from odoo.addons.queue_job.fields import JobEncoder, JobDecoder


class TestJson(common.TransactionCase):

    def test_encoder_recordset(self):
        value = ['a', 1, self.env.ref('base.user_root')]
        value_json = json.dumps(value, cls=JobEncoder)
        expected = ('["a", 1, {"_type": "odoo_recordset", '
                    '"model": "res.users", "ids": [1]}]')
        self.assertEqual(value_json, expected)

    def test_decoder_recordset(self):
        value_json = ('["a", 1, {"_type": "odoo_recordset",'
                      '"model": "res.users", "ids": [1]}]')
        expected = ['a', 1, self.env.ref('base.user_root')]
        value = json.loads(value_json, cls=JobDecoder, env=self.env)
        self.assertEqual(value, expected)

    def test_encoder_datetime(self):
        value = ['a', 1, datetime(2017, 4, 19, 8, 48, 50, 1)]
        value_json = json.dumps(value, cls=JobEncoder)
        expected = ('["a", 1, {"_type": "datetime_isoformat", '
                    '"value": "2017-04-19T08:48:50.000001"}]')
        self.assertEqual(value_json, expected)

    def test_decoder_datetime(self):
        value_json = ('["a", 1, {"_type": "datetime_isoformat",'
                      '"value": "2017-04-19T08:48:50.000001"}]')
        expected = ['a', 1, datetime(2017, 4, 19, 8, 48, 50, 1)]
        value = json.loads(value_json, cls=JobDecoder, env=self.env)
        self.assertEqual(value, expected)

    def test_encoder_date(self):
        value = ['a', 1, date(2017, 4, 19)]
        value_json = json.dumps(value, cls=JobEncoder)
        expected = ('["a", 1, {"_type": "date_isoformat", '
                    '"value": "2017-04-19"}]')
        self.assertEqual(value_json, expected)

    def test_decoder_date(self):
        value_json = ('["a", 1, {"_type": "date_isoformat",'
                      '"value": "2017-04-19"}]')
        expected = ['a', 1, date(2017, 4, 19)]
        value = json.loads(value_json, cls=JobDecoder, env=self.env)
        self.assertEqual(value, expected)
