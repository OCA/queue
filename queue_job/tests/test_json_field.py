# copyright 2016 Camptocamp
# license lgpl-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import json
from datetime import date, datetime

from odoo.tests import common

# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
from odoo.addons.queue_job.fields import JobDecoder, JobEncoder


class TestJson(common.TransactionCase):
    def test_encoder_recordset(self):
        demo_user = self.env.ref("base.user_demo")
        partner = self.env(user=demo_user).ref("base.main_partner")
        value = ["a", 1, partner]
        value_json = json.dumps(value, cls=JobEncoder)
        expected = [
            "a",
            1,
            {
                "uid": demo_user.id,
                "_type": "odoo_recordset",
                "model": "res.partner",
                "ids": [partner.id],
            },
        ]
        self.assertEqual(json.loads(value_json), expected)

    def test_decoder_recordset(self):
        demo_user = self.env.ref("base.user_demo")
        partner = self.env(user=demo_user).ref("base.main_partner")
        value_json = (
            '["a", 1, '
            '{"_type": "odoo_recordset",'
            '"model": "res.partner",'
            '"ids": [%s],"uid": %s}]' % (partner.id, demo_user.id)
        )
        expected = ["a", 1, partner]
        value = json.loads(value_json, cls=JobDecoder, env=self.env)
        self.assertEqual(value, expected)
        self.assertEqual(demo_user, expected[2].env.user)

    def test_decoder_recordset_without_user(self):
        value_json = (
            '["a", 1, {"_type": "odoo_recordset",' '"model": "res.users", "ids": [1]}]'
        )
        expected = ["a", 1, self.env.ref("base.user_root")]
        value = json.loads(value_json, cls=JobDecoder, env=self.env)
        self.assertEqual(value, expected)

    def test_encoder_datetime(self):
        value = ["a", 1, datetime(2017, 4, 19, 8, 48, 50, 1)]
        value_json = json.dumps(value, cls=JobEncoder)
        expected = [
            "a",
            1,
            {"_type": "datetime_isoformat", "value": "2017-04-19T08:48:50.000001"},
        ]
        self.assertEqual(json.loads(value_json), expected)

    def test_decoder_datetime(self):
        value_json = (
            '["a", 1, {"_type": "datetime_isoformat",'
            '"value": "2017-04-19T08:48:50.000001"}]'
        )
        expected = ["a", 1, datetime(2017, 4, 19, 8, 48, 50, 1)]
        value = json.loads(value_json, cls=JobDecoder, env=self.env)
        self.assertEqual(value, expected)

    def test_encoder_date(self):
        value = ["a", 1, date(2017, 4, 19)]
        value_json = json.dumps(value, cls=JobEncoder)
        expected = ["a", 1, {"_type": "date_isoformat", "value": "2017-04-19"}]
        self.assertEqual(json.loads(value_json), expected)

    def test_decoder_date(self):
        value_json = '["a", 1, {"_type": "date_isoformat",' '"value": "2017-04-19"}]'
        expected = ["a", 1, date(2017, 4, 19)]
        value = json.loads(value_json, cls=JobDecoder, env=self.env)
        self.assertEqual(value, expected)
