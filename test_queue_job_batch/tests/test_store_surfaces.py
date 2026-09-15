# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests.common import HttpCase, TransactionCase, new_test_user, tagged

from odoo.addons.mail.tools.discuss import Store


class TestBatchStoreData(TransactionCase):
    """The store payload the web client relies on to draw the systray."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.batch = cls.env["queue.job.batch"].get_new_batch("TEST STORE")

    def test_the_batch_is_stored_with_its_progress_fields(self):
        """`_to_store_defaults` decides what the systray can draw.

        The migration replaced a hand-written read of these fields by
        `_to_store_defaults`. Dropping one of them leaves the client without the
        value and the progress bar silently renders empty, so the contract is
        the list itself.
        """
        result = Store().add(self.batch).get_result()
        self.assertIn("queue.job.batch", result)
        stored = result["queue.job.batch"][0]
        self.assertEqual(stored["id"], self.batch.id)
        for field in (
            "name",
            "state",
            "job_count",
            "finished_job_count",
            "failed_job_count",
            "completeness",
            "failed_percentage",
        ):
            self.assertIn(
                field,
                stored,
                f"'{field}' is not in the store payload: the client cannot draw "
                f"what it is not given",
            )
        self.assertEqual(stored["name"], "TEST STORE")
        self.assertEqual(stored["state"], self.batch.state)

    def test_a_user_in_the_group_is_told_so(self):
        """`hasQueueJobBatchUserGroup` is what makes the systray appear at all."""
        user = new_test_user(
            self.env,
            login="batch_user",
            groups="base.group_user,queue_job_batch.group_queue_job_batch_user",
        )
        store = Store()
        self.env["res.users"].with_user(user)._init_store_data(store)
        self.assertTrue(
            store.get_result()["Store"]["hasQueueJobBatchUserGroup"],
            "a member of the group was not told so: the systray never shows up",
        )

    def test_a_user_outside_the_group_is_told_so(self):
        """The negative side: without it the flag would be useless."""
        user = new_test_user(self.env, login="plain_user", groups="base.group_user")
        store = Store()
        self.env["res.users"].with_user(user)._init_store_data(store)
        self.assertFalse(
            store.get_result()["Store"]["hasQueueJobBatchUserGroup"],
            "a user outside the group was told otherwise",
        )


@tagged("-at_install", "post_install")
class TestBatchSystrayRequest(HttpCase):
    """The systray request over /mail/data.

    In 19.0 the request is dispatched **by name** instead of by a keyword flag,
    so a test that only checked the payload would not notice the controller
    answering every request.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env,
            login="systray_user",
            password="systray_user",
            groups="base.group_user,queue_job_batch.group_queue_job_batch_user",
        )
        cls.batch = (
            cls.env["queue.job.batch"].with_user(cls.user).get_new_batch("TEST SYSTRAY")
        )

    def test_the_systray_request_returns_the_unread_batches(self):
        self.authenticate("systray_user", "systray_user")
        data = self.make_jsonrpc_request(
            "/mail/data", {"fetch_params": ["systray_get_queue_job_batches"]}
        )
        self.assertEqual(
            data["Store"]["queueJobBatchCounter"],
            1,
            "the counter does not match the unread batches of the user",
        )
        self.assertIn(
            "queueJobBatchCounterBusId",
            data["Store"],
            "without the bus id the client cannot tell a stale counter from a "
            "fresh one",
        )
        # Guarded before indexing: a bare KeyError here says nothing to whoever
        # reads the red.
        self.assertIn(
            "queue.job.batch",
            data,
            "the batch itself was not sent, only its count: the systray has a "
            "number it cannot open",
        )
        self.assertEqual(
            [batch["id"] for batch in data["queue.job.batch"]],
            [self.batch.id],
        )

    def test_another_request_does_not_get_the_batch_counter(self):
        """Guard against answering every request instead of its own.

        This is the shape of the 19.0 change: dispatch by `name`. If the guard
        goes, the counter rides along on unrelated requests.
        """
        self.authenticate("systray_user", "systray_user")
        data = self.make_jsonrpc_request(
            "/mail/data", {"fetch_params": ["systray_get_activities"]}
        )
        self.assertNotIn(
            "queueJobBatchCounter",
            data.get("Store", {}),
            "the batch counter answered a request that did not ask for it",
        )
