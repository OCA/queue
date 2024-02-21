# license lgpl-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
from odoo.tests import common


class TestWizards(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Remove this variable in v16 and put instead:
        # from odoo.addons.base.tests.common import DISABLED_MAIL_CONTEXT
        DISABLED_MAIL_CONTEXT = {
            "tracking_disable": True,
            "mail_create_nolog": True,
            "mail_create_nosubscribe": True,
            "mail_notrack": True,
            "no_reset_password": True,
        }
        cls.env = cls.env(context=dict(cls.env.context, **DISABLED_MAIL_CONTEXT))
        cls.job = (
            cls.env["queue.job"]
            .with_context(
                _job_edit_sentinel=cls.env["queue.job"].EDIT_SENTINEL,
            )
            .create(
                {
                    "uuid": "test",
                    "user_id": cls.env.user.id,
                    "state": "failed",
                    "model_name": "queue.job",
                    "method_name": "write",
                    "args": (),
                }
            )
        )

    def _wizard(self, model_name):
        return (
            self.env[model_name]
            .with_context(
                active_model=self.job._name,
                active_ids=self.job.ids,
            )
            .create({})
        )

    def test_01_requeue(self):
        wizard = self._wizard("queue.requeue.job")
        wizard.requeue()
        self.assertEqual(self.job.state, "pending")

    def test_02_cancel(self):
        wizard = self._wizard("queue.jobs.to.cancelled")
        wizard.set_cancelled()
        self.assertEqual(self.job.state, "cancelled")

    def test_03_done(self):
        wizard = self._wizard("queue.jobs.to.done")
        wizard.set_done()
        self.assertEqual(self.job.state, "done")
