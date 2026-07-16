# Copyright 2026 QoQa Services SA (https://www.qoqa.ch)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo.tests.common import TransactionCase

from ..job import Job, JobStore


class TestJobPayload(TransactionCase):
    def test_payload_binds_recordset_and_args(self):
        partner1 = self.env["res.partner"].create({"name": "one"})
        partner2 = self.env["res.partner"].create({"name": "two"})
        job = partner1.with_delay().concat(partner2)

        JobStore(self.env).save(job)
        self.env.flush_all()

        other_env = self.env(context=dict(self.env.context, _other_env=True))

        loaded = Job.load(other_env, job.uuid)
        payload = loaded.payload(other_env)

        self.assertEqual(payload.recordset, partner1)
        self.assertEqual(payload.args[0], partner2)

        for record in (payload.recordset, *payload.args):
            self.assertIs(record.env.cr, other_env.cr)
            self.assertIs(record.env.transaction, other_env.transaction)

        # the same job binds the payload to a different env on another call
        again = loaded.payload(self.env)
        self.assertIs(again.recordset.env.transaction, self.env.transaction)
