# license lgpl-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
from odoo.tests import common


class TestWizards(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.job = (
            self.env["queue.job"]
            .with_context(
                _job_edit_sentinel=self.env["queue.job"].EDIT_SENTINEL,
            )
            .create(
                {
                    "uuid": "test",
                    "user_id": self.env.user.id,
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

    def test_04_requeue_forbidden(self):
        wizard = self._wizard("queue.requeue.job")

        # State WAIT_DEPENDENCIES is not requeued
        self.job.state = "wait_dependencies"
        wizard.requeue()
        self.assertEqual(self.job.state, "wait_dependencies")

        # State PENDING, ENQUEUED or STARTED are ignored too
        for test_state in ("pending", "enqueued", "started"):
            self.job.state = test_state
            wizard.requeue()
            self.assertEqual(self.job.state, test_state)

        # States CANCELLED, DONE or FAILED will change status
        self.job.state = "cancelled"
        wizard.requeue()
        self.assertEqual(self.job.state, "pending")

    def test_05_cancel_forbidden(self):
        wizard = self._wizard("queue.jobs.to.cancelled")

        # State WAIT_DEPENDENCIES is not cancelled
        self.job.state = "wait_dependencies"
        wizard.set_cancelled()
        self.assertEqual(self.job.state, "wait_dependencies")

        # State DONE is not cancelled
        self.job.state = "done"
        wizard.set_cancelled()
        self.assertEqual(self.job.state, "done")

        # State PENDING, ENQUEUED or FAILED will be cancelled
        for test_state in ("pending", "enqueued"):
            self.job.state = test_state
            wizard.set_cancelled()
            self.assertEqual(self.job.state, "cancelled")

    def test_06_done_forbidden(self):
        wizard = self._wizard("queue.jobs.to.done")

        # State STARTED is not set DONE manually
        self.job.state = "started"
        wizard.set_done()
        self.assertEqual(self.job.state, "started")

        # State CANCELLED is not cancelled
        self.job.state = "cancelled"
        wizard.set_done()
        self.assertEqual(self.job.state, "cancelled")

        # State WAIT_DEPENDENCIES, PENDING, ENQUEUED or FAILED will be set to DONE
        for test_state in ("wait_dependencies", "pending", "enqueued"):
            self.job.state = test_state
            wizard.set_done()
            self.assertEqual(self.job.state, "done")
