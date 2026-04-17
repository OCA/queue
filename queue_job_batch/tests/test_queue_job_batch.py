# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from types import SimpleNamespace
from unittest import mock

from odoo.tests import common
from odoo.tools import mute_logger

from odoo.addons.mail.tools.discuss import Store

from ..controllers import main as batch_main
from ..controllers import webclient as batch_webclient
from ..controllers.main import RunJobBatchController
from ..controllers.webclient import WebClient


class TestQueueJobBatchStoreData(common.TransactionCase):
    def test_init_store_data_sets_batch_globals(self):
        batch_group = self.env.ref("queue_job_batch.group_queue_job_batch_user")
        self.env.user.write({"group_ids": [(4, batch_group.id)]})
        self.env["queue.job.batch"].sudo().create(
            {
                "name": "Batch",
                "user_id": self.env.user.id,
                "company_id": self.env.company.id,
                "is_read": False,
            }
        )

        store = Store()
        self.env["res.users"]._init_store_data(store)
        store_data = store.get_result()["Store"]

        self.assertTrue(store_data["hasQueueJobBatchUserGroup"])
        self.assertEqual(store_data["queueJobBatchCounter"], 1)
        self.assertIn("queueJobBatchCounterBusId", store_data)


class TestQueueJobBatchCreatePrivate(common.HttpCase):
    def test_queue_job_create_stays_private(self):
        self.authenticate("admin", "admin")
        with self.assertRaises(common.JsonRpcException) as cm, mute_logger("odoo.http"):
            self.make_jsonrpc_request(
                "/web/dataset/call_kw",
                params={
                    "model": "queue.job",
                    "method": "create",
                    "args": [],
                    "kwargs": {
                        "method_name": "write",
                        "model_name": "res.partner",
                        "uuid": "test",
                    },
                },
            )
        self.assertEqual("odoo.exceptions.AccessError", str(cm.exception))


class TestQueueJobBatchController(common.TransactionCase):
    def test_create_test_batch_jobs_links_jobs_to_batch(self):
        batch, job_uuids = RunJobBatchController._create_test_batch_jobs(
            self.env,
            size=3,
            description="Batch smoke test",
            batch_name="Batch smoke test",
        )

        jobs = self.env["queue.job"].search([("uuid", "in", job_uuids)])

        self.assertEqual(3, len(job_uuids))
        self.assertEqual(3, len(jobs))
        self.assertEqual(3, batch.job_count)
        self.assertEqual({batch.id}, set(jobs.mapped("job_batch_id").ids))

    def test_parse_helpers_fallback_to_defaults(self):
        self.assertEqual(7, RunJobBatchController._parse_int("7", 0))
        self.assertEqual(3, RunJobBatchController._parse_int(None, 3))
        self.assertEqual(3, RunJobBatchController._parse_int("bad", 3))
        self.assertEqual(1.5, RunJobBatchController._parse_float("1.5", 0))
        self.assertEqual(2.5, RunJobBatchController._parse_float(None, 2.5))
        self.assertEqual(2.5, RunJobBatchController._parse_float("bad", 2.5))

    def test_create_test_batch_rejects_non_managers(self):
        env = SimpleNamespace(
            user=SimpleNamespace(has_group=lambda group: False),
            _=lambda msg: msg,
        )

        with mock.patch.object(batch_main.http, "request", SimpleNamespace(env=env)):
            with self.assertRaises(batch_main.Forbidden):
                RunJobBatchController().create_test_batch()

    def test_create_test_batch_validates_failure_rate(self):
        env = SimpleNamespace(
            user=SimpleNamespace(has_group=lambda group: True),
            _=lambda msg: msg,
        )

        with mock.patch.object(batch_main.http, "request", SimpleNamespace(env=env)):
            with self.assertRaises(batch_main.BadRequest):
                RunJobBatchController().create_test_batch(failure_rate=2)

    def test_create_test_batch_returns_empty_for_non_positive_size(self):
        env = SimpleNamespace(
            user=SimpleNamespace(has_group=lambda group: True),
            _=lambda msg: msg,
        )

        with mock.patch.object(batch_main.http, "request", SimpleNamespace(env=env)):
            result = RunJobBatchController().create_test_batch(size=0)

        self.assertEqual(200, result.status_code)
        self.assertEqual("", result.get_data(as_text=True))

    def test_create_test_batch_returns_batch_summary(self):
        env = SimpleNamespace(
            user=SimpleNamespace(has_group=lambda group: True),
            _=lambda msg: msg,
        )
        fake_batch = SimpleNamespace(id=42)

        with mock.patch.object(batch_main.http, "request", SimpleNamespace(env=env)):
            with mock.patch.object(
                RunJobBatchController,
                "_create_test_batch_jobs",
                return_value=(fake_batch, ["a", "b"]),
            ) as create_jobs:
                result = RunJobBatchController().create_test_batch(
                    size="2",
                    priority="3",
                    max_retries="4",
                    failure_rate="0.5",
                    job_duration="1.25",
                    failure_retry_seconds="9",
                    description="Smoke",
                    batch_name="Batch smoke",
                )

        self.assertEqual(200, result.status_code)
        self.assertEqual("batch id: 42, jobs: 2", result.get_data(as_text=True))
        create_jobs.assert_called_once_with(
            env,
            size=2,
            priority=3,
            max_retries=4,
            channel=None,
            description="Smoke",
            batch_name="Batch smoke",
            failure_rate=0.5,
            job_duration=1.25,
            commit_within_job=False,
            failure_retry_seconds=9,
        )


class TestQueueJobBatchWebclient(common.TransactionCase):
    def test_process_request_for_internal_user_adds_batch_store_values(self):
        class FakeEnv(dict):
            pass

        fake_batches = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        fake_user = SimpleNamespace(_get_queue_job_batches=lambda: fake_batches)
        fake_bus = SimpleNamespace(
            sudo=lambda: SimpleNamespace(_bus_last_id=lambda: 99)
        )
        fake_env = FakeEnv({"bus.bus": fake_bus})
        fake_env.user = fake_user
        fake_request = SimpleNamespace(env=fake_env)
        store = mock.Mock()

        with mock.patch.object(
            batch_webclient.WebclientController,
            "_process_request_for_internal_user",
            return_value="parent-result",
        ) as super_call:
            with mock.patch.object(batch_webclient, "request", fake_request):
                result = WebClient._process_request_for_internal_user(
                    store,
                    "systray_get_queue_job_batches",
                    {},
                )

        self.assertEqual("parent-result", result)
        super_call.assert_called_once_with(store, "systray_get_queue_job_batches", {})
        store.add.assert_called_once_with(fake_batches)
        store.add_global_values.assert_called_once_with(
            queueJobBatchCounter=2,
            queueJobBatchCounterBusId=99,
        )

    def test_process_request_for_internal_user_skips_non_batch_requests(self):
        store = mock.Mock()

        with mock.patch.object(
            batch_webclient.WebclientController,
            "_process_request_for_internal_user",
            return_value="parent-result",
        ) as super_call:
            with mock.patch.object(batch_webclient, "request", mock.Mock()):
                result = WebClient._process_request_for_internal_user(
                    store,
                    "other_request",
                    {},
                )

        self.assertEqual("parent-result", result)
        super_call.assert_called_once_with(store, "other_request", {})
        store.add.assert_not_called()
        store.add_global_values.assert_not_called()
