# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
import os
import socket
from unittest.mock import MagicMock, patch

import requests

from odoo.tests import common

from ..jobrunner import (
    ENQUEUED,
    PENDING,
    Database,
    QueueJobRunner,
    _async_http_get,
    _channels,
    _connection_info_for,
    _logger,
    start_async_http_get,
)
from .common import JobMixin


class TestQueueJobRunnerUpdates(common.TransactionCase, JobMixin):
    def setUp(self):
        super().setUp()
        self.runner = QueueJobRunner()

    def test_channels_from_env(self):
        with patch.dict(os.environ, {"ODOO_QUEUE_JOB_CHANNELS": "root:4"}):
            self.assertEqual(_channels(), "root:4")

    def test_channels_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_channels(), "root:1")

    def test_connection_info_for(self):
        with patch.dict(
            os.environ, {"ODOO_QUEUE_JOB_JOBRUNNER_DB_HOST": "custom_host"}
        ):
            with patch("odoo.sql_db.connection_info_for") as mock_connection_info_for:
                mock_connection_info_for.return_value = ("db_name", {})
                connection_info = _connection_info_for("test_db")
                self.assertEqual(connection_info["host"], "custom_host")

    def test_async_http_get_success(self):
        with patch("requests.get") as mock_get:
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn
                mock_get.return_value.status_code = 200
                _async_http_get(
                    "http", "localhost", 8069, None, None, "test_db", "test_uuid"
                )
                mock_get.assert_called_once()
                mock_conn.cursor().execute.assert_not_called()

    def test_async_http_get_timeout(self):
        with patch("requests.get", side_effect=requests.Timeout) as mock_get:
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn
                mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
                _async_http_get(
                    "http", "localhost", 8069, None, None, "test_db", "test_uuid"
                )
                mock_get.assert_called_once()
                mock_cursor.execute.assert_called_once_with(
                    """
                    UPDATE queue_job 
                    SET state=%s, date_enqueued=NULL, date_started=NULL 
                    WHERE uuid=%s AND state=%s 
                    RETURNING uuid
                    """,
                    (PENDING, "test_uuid", ENQUEUED),
                )

    def test_create_socket_pair(self):
        recv, send = self.runner._create_socket_pair()
        self.assertIsInstance(recv, socket.socket)
        self.assertIsInstance(send, socket.socket)

    def test_initialize_databases(self):
        with patch.object(
            QueueJobRunner, "get_db_names", return_value=["test_db1", "test_db2"]
        ):
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn
                with patch.object(self.runner.channel_manager, "notify") as mock_notify:
                    self.runner.initialize_databases()
                    self.assertIn("test_db1", self.runner.db_by_name)
                    self.assertIn("test_db2", self.runner.db_by_name)
                    mock_notify.assert_called()

    def test_run_jobs(self):
        with patch("psycopg2.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            self.runner.db_by_name = {"test_db": mock_conn}
            mock_job = MagicMock()
            mock_job.uuid = "test_uuid"
            mock_job.db_name = "test_db"
            with patch.object(
                self.runner.channel_manager, "get_jobs_to_run", return_value=[mock_job]
            ):
                with patch(
                    "odoo.addons.queue_job.jobrunner._async_http_get"
                ) as mock_async_get:
                    self.runner.run_jobs()
                mock_conn.cursor().execute.assert_called_with(
                    """
                    UPDATE queue_job 
                    SET state=%s, 
                        date_enqueued=date_trunc('seconds', now() at time zone 'utc')
                    WHERE uuid=%s
                    """,
                    (ENQUEUED, "test_uuid"),
                )
                mock_async_get.assert_called_once_with(
                    "http", "localhost", 8069, None, None, "test_db", "test_uuid"
                )

    def test_async_http_get_invalid_url(self):
        with patch("requests.get", side_effect=requests.RequestException) as mock_get:
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn
                mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
                _async_http_get(
                    "http", "invalid_host", 8069, None, None, "test_db", "test_uuid"
                )
                mock_get.assert_called_once()
                mock_cursor.execute.assert_called_once_with(
                    """
                    UPDATE queue_job 
                    SET state=%s, 
                        date_enqueued=NULL, date_started=NULL 
                    WHERE uuid=%s and state=%s 
                    RETURNING uuid
                    """,
                    (PENDING, "test_uuid", ENQUEUED),
                )

    def test_wait_notification(self):
        with patch("time.sleep", return_value=None):
            mock_conn = MagicMock()
            self.runner.db_by_name = {"test_db": mock_conn}
            mock_conn.poll.return_value = 1
            self.runner.wait_notification()
            mock_conn.poll.assert_called_once()

    def test_process_notifications(self):
        with patch("time.sleep", return_value=None):
            mock_conn = MagicMock()
            self.runner.db_by_name = {"test_db": mock_conn}
            mock_conn.notifies = [MagicMock()]
            with patch.object(self.runner.channel_manager, "notify"):
                self.runner.process_notifications()
            self.assertFalse(mock_conn.notifies)

    def test_run(self):
        with patch("time.sleep", return_value=None):
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn
                with (
                    patch.object(self.runner, "initialize_databases") as mock_init,
                    patch.object(self.runner, "close_databases") as mock_close,
                ):
                    self.runner.run()
                    mock_init.assert_called_once()
                    mock_close.assert_called_once()

    def test_stop(self):
        self.runner.stop()
        self.assertTrue(self.runner._stop)
        recv, send = self.runner._create_socket_pair()
        self.assertTrue(send.send(b"stop"))

    def test_handle_exceptions_in_run(self):
        with patch("time.sleep", return_value=None):
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn
                with (
                    patch.object(self.runner, "initialize_databases") as mock_init,
                    patch.object(self.runner, "close_databases") as mock_close,
                ):
                    with patch.object(
                        self.runner, "process_notifications", side_effect=Exception
                    ):
                        self.runner.run()
                        mock_init.assert_called_once()
                        mock_close.assert_called_once()

    def test_async_http_get_client_error(self):
        with patch("requests.get", side_effect=requests.RequestException) as mock_get:
            with patch("psycopg2.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn
                mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
                _async_http_get(
                    "http", "localhost", 8069, None, None, "test_db", "test_uuid"
                )
                mock_get.assert_called_once()
                mock_cursor.execute.assert_called_once_with(
                    """
                    UPDATE queue_job 
                    SET state=%s, date_enqueued=NULL, date_started=NULL 
                    WHERE uuid=%s AND state=%s 
                    RETURNING uuid
                    """,
                    (PENDING, "test_uuid", ENQUEUED),
                )

    def test_start_async_http_get_event_loop_running(self):
        with patch(
            "odoo.addons.queue_job.jobrunner.asyncio.get_event_loop"
        ) as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = True
            mock_get_loop.return_value = mock_loop
            start_async_http_get(
                "http", "localhost", 8069, None, None, "test_db", "test_uuid"
            )
            mock_loop.create_task.assert_called_once()

    def test_start_async_http_get_event_loop_not_running(self):
        with patch("odoo.addons.queue_job.jobrunner.asyncio.run") as mock_run:
            start_async_http_get(
                "http", "localhost", 8069, None, None, "test_db", "test_uuid"
            )
            mock_run.assert_called_once()

    def test_database_initialization_failure(self):
        with patch("psycopg2.connect", side_effect=Exception("Connection failed")):
            with self.assertLogs(_logger, level="ERROR") as log:
                db = Database("test_db")
                self.assertIsNone(db.conn)
                self.assertIn("Connection failed", log.output[0])

    def test_create_socket_pair_compatibility(self):
        with patch(
            "odoo.addons.queue_job.jobrunner.socket.socketpair",
            side_effect=AttributeError,
        ):
            recv, send = self.runner._create_socket_pair()
            self.assertIsInstance(recv, socket.socket)
            self.assertIsInstance(send, socket.socket)
            self.assertEqual(recv.getsockname()[0], "127.0.0.1")

    def test_run_event_loop_start_stop(self):
        runner = QueueJobRunner()
        runner.loop.call_soon_threadsafe = MagicMock()
        runner.loop.stop = MagicMock()
        runner._stop = True
        runner._run_event_loop()
        runner.loop.stop.assert_called_once()

    def test_handle_db_notifications(self):
        mock_conn = MagicMock()
        self.runner.db_by_name = {"test_db": mock_conn}
        mock_notify = MagicMock()
        self.runner.channel_manager.notify = mock_notify
        mock_notify_payload = MagicMock()
        mock_conn.notifies = [mock_notify_payload]

        self.runner.process_notifications()

        self.assertFalse(mock_conn.notifies)
        mock_notify.assert_called_once_with("test_db", *mock_notify_payload)

    def test_check_new_databases_periodically(self):
        with patch.object(
            self.runner, "check_and_initialize_new_databases"
        ) as mock_check:
            with patch("time.sleep", side_effect=Exception("stop")):
                with self.assertRaisesRegex(Exception, "stop"):
                    self.runner._check_new_databases_periodically()
                mock_check.assert_called()
