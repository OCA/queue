# copyright 2022 Guewen Baconnier
# license lgpl-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import json

from odoo.tests import common

# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as if we were an external consumer of the API
from odoo.addons.queue_job.fields import JobEncoder


class TestJsonField(common.TransactionCase):

    # TODO: when migrating to 16.0, adapt the checks in queue_job/tests/test_json_field.py
    # to verify the context keys are encoded and remove these
    def test_encoder_recordset_store_context(self):
        demo_user = self.env.ref("base.user_demo")
        user_context = {"lang": "en_US", "tz": "Europe/Brussels"}
        test_model = self.env(user=demo_user, context=user_context)["test.queue.job"]
        value_json = json.dumps(test_model, cls=JobEncoder)
        self.assertEqual(json.loads(value_json)["context"], user_context)

    def test_encoder_recordset_context_filter_keys(self):
        demo_user = self.env.ref("base.user_demo")
        user_context = {"lang": "en_US", "tz": "Europe/Brussels"}
        tampered_context = dict(user_context, foo=object())
        test_model = self.env(user=demo_user, context=tampered_context)[
            "test.queue.job"
        ]
        value_json = json.dumps(test_model, cls=JobEncoder)
        self.assertEqual(json.loads(value_json)["context"], user_context)
