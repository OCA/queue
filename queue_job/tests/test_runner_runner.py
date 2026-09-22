# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
import doctest
import os
from unittest import mock

from odoo.tests import BaseCase, tagged
from odoo.tools import mute_logger

from odoo.addons.queue_job.jobrunner import runner

# pylint: disable=odoo-addons-relative-import
# we are testing, we want to test as we were an external consumer of the API
from odoo.addons.queue_job.jobrunner.channels import ChannelConfig, ChannelManager


@tagged("doctest")
class TestDoctest(BaseCase):
    def test_doctest(self):
        results = doctest.testmod(
            runner, exclude_empty=True, optionflags=doctest.REPORT_ONLY_FIRST_FAILURE
        )
        self.assertEqual(results.failed, 0, "doctest failed")


@tagged("-at_install", "post_install")
class TestRunner(BaseCase):
    def setUp(self):
        super().setUp()
        # ensure there is no collision with actual environment variables/config
        env_patcher = mock.patch.dict(
            "os.environ",
            {
                "ODOO_QUEUE_JOB_MAX_CAPACITY": "",
                "ODOO_QUEUE_JOB_DB_MAX_CAPACITY": "",
                "ODOO_QUEUE_JOB_CHANNELS": "",
            },
        )
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

        conf_patcher = mock.patch.object(runner, "queue_job_config", {})
        conf_patcher.start()
        self.addCleanup(conf_patcher.stop)

    @staticmethod
    def _mock_db(db_name, channels_config):
        """Mock a Database

        :param channels_config: list of ChannelConfig as configured in the DB
        """
        return mock.MagicMock(
            db_name=db_name,
            has_queue_job=True,
            load_channels_config=mock.MagicMock(return_value=channels_config),
        )

    def _register_channel_manager(self, jobrunner, db_name, channel_manager):
        jobrunner._channel_manager_by_db[db_name] = channel_manager
        jobrunner._channel_managers.append(channel_manager)

    def _new_channel_manager(self, jobrunner, db_name, channel_config, pending_jobs=0):
        channel_manager = ChannelManager()
        channel_manager.configure(channel_config)
        self._register_channel_manager(jobrunner, db_name, channel_manager)
        jobrunner.db_by_name[db_name] = self._mock_db(db_name, channel_config)
        for number in range(pending_jobs):
            channel_manager.notify(
                db_name, "root", f"{db_name}-{number}", number, 0, 10, None, "pending"
            )
        return channel_manager

    @classmethod
    def _is_open_file_descriptor(cls, fd):
        try:
            os.fstat(fd)
            return True
        except OSError:
            return False

    def test_runner_file_descriptor(self):
        a_runner = runner.QueueJobRunner.from_environ_or_config()

        read_fd, write_fd = a_runner._stop_pipe
        self.assertTrue(self._is_open_file_descriptor(read_fd))
        self.assertTrue(self._is_open_file_descriptor(write_fd))

        del a_runner

        self.assertFalse(self._is_open_file_descriptor(read_fd))
        self.assertFalse(self._is_open_file_descriptor(write_fd))

    def test_runner_file_closed_read_descriptor(self):
        a_runner = runner.QueueJobRunner.from_environ_or_config()

        read_fd, write_fd = a_runner._stop_pipe
        os.close(read_fd)

        del a_runner

        self.assertFalse(self._is_open_file_descriptor(read_fd))
        self.assertFalse(self._is_open_file_descriptor(write_fd))

    def test_runner_file_closed_write_descriptor(self):
        a_runner = runner.QueueJobRunner.from_environ_or_config()

        read_fd, write_fd = a_runner._stop_pipe
        os.close(write_fd)

        del a_runner

        self.assertFalse(self._is_open_file_descriptor(read_fd))
        self.assertFalse(self._is_open_file_descriptor(write_fd))

    def test_max_capacity_from_env(self):
        with (
            mock.patch.dict(
                os.environ, {"ODOO_QUEUE_JOB_MAX_CAPACITY": "5"}, clear=True
            ),
            mock.patch.object(runner, "queue_job_config", {}),
        ):
            self.assertEqual(runner._max_capacity(), 5)

    def test_max_capacity_from_odoo_config(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(runner, "queue_job_config", {"max_capacity": "3"}),
        ):
            self.assertEqual(runner._max_capacity(), 3)

    def test_max_capacity_env_priority_over_odoo_config(self):
        with (
            mock.patch.dict(
                os.environ, {"ODOO_QUEUE_JOB_MAX_CAPACITY": "5"}, clear=True
            ),
            mock.patch.object(runner, "queue_job_config", {"max_capacity": "3"}),
        ):
            self.assertEqual(runner._max_capacity(), 5)

    def test_max_capacity_default(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(runner, "queue_job_config", {}),
        ):
            self.assertEqual(runner._max_capacity(), 1)

    def test_max_capacity_zero(self):
        with (
            mock.patch.dict(
                os.environ, {"ODOO_QUEUE_JOB_MAX_CAPACITY": "0"}, clear=True
            ),
            mock.patch.object(runner, "queue_job_config", {}),
        ):
            self.assertEqual(runner._max_capacity(), 0)

    def test_db_max_capacity_from_env(self):
        with (
            mock.patch.dict(
                os.environ, {"ODOO_QUEUE_JOB_DB_MAX_CAPACITY": "prod_*:20,*:5"}
            ),
            mock.patch.object(runner, "queue_job_config", {}),
        ):
            self.assertEqual(runner._db_max_capacity(), "prod_*:20,*:5")

    def test_db_max_capacity_from_odoo_config(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(
                runner, "queue_job_config", {"db_max_capacity": "prod_*:20,*:5"}
            ),
        ):
            self.assertEqual(runner._db_max_capacity(), "prod_*:20,*:5")

    def test_db_max_capacity_env_priority_over_odoo_config(self):
        with (
            mock.patch.dict(os.environ, {"ODOO_QUEUE_JOB_DB_MAX_CAPACITY": "*:5"}),
            mock.patch.object(runner, "queue_job_config", {"db_max_capacity": "*:3"}),
        ):
            self.assertEqual(runner._db_max_capacity(), "*:5")

    def test_db_max_capacity_default(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(runner, "queue_job_config", {}),
        ):
            self.assertEqual(runner._db_max_capacity(), "")

    def test_max_capacity_negative(self):
        jobrunner = runner.QueueJobRunner(max_capacity=-5)
        self.assertEqual(jobrunner.max_capacity, 0)

    def test_max_capacity_equals_to_channel_config_string(self):
        jobrunner = runner.QueueJobRunner(channel_config_string="root:3")
        self.assertEqual(jobrunner.max_capacity, 3)

    def test_max_capacity_server_wide_has_priority(self):
        jobrunner = runner.QueueJobRunner(
            channel_config_string="root:3", max_capacity=1
        )
        self.assertEqual(jobrunner.max_capacity, 3)

    def test_max_capacity_channel_config_no_root(self):
        jobrunner = runner.QueueJobRunner(channel_config_string="sub:3")
        self.assertEqual(jobrunner.max_capacity, 1)

    def test_no_job_dispatched_when_no_database_channel_manager(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        with mock.patch.object(jobrunner, "_dispatch_job") as dispatch:
            jobrunner.run_jobs()
        dispatch.assert_not_called()

    def test_global_capacity_across_databases(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        manager_a = self._new_channel_manager(
            jobrunner, "db_a", [ChannelConfig("root", 5)], pending_jobs=4
        )
        manager_b = self._new_channel_manager(
            jobrunner, "db_b", [ChannelConfig("root", 5)], pending_jobs=4
        )
        with mock.patch.object(jobrunner, "_dispatch_job") as dispatch:
            jobrunner.run_jobs()
        # number of running jobs must be limited by max_capacity
        self.assertEqual(dispatch.call_count, 3)
        self.assertEqual(manager_a.running_count + manager_b.running_count, 3)

    def test_round_robin(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        self._new_channel_manager(
            jobrunner, "db_a", [ChannelConfig("root", 3)], pending_jobs=2
        )
        self._new_channel_manager(
            jobrunner, "db_b", [ChannelConfig("root", 3)], pending_jobs=2
        )
        dispatched = []
        with mock.patch.object(
            jobrunner, "_dispatch_job", side_effect=lambda job: dispatched.append(job)
        ):
            jobrunner.run_jobs()
            # with max_capacity=3 and 2 pending jobs per db, the first
            # run_jobs() will dispatch 3 jobs in alternating order
            self.assertEqual(
                [job.db_name for job in dispatched], ["db_a", "db_b", "db_a"]
            )
            # notify the first dispatched job as done so a slot is freed up
            # so we can check that the next call to run_jobs() continues
            # to round-robin
            jobrunner._channel_manager_by_db[dispatched[0].db_name].notify(
                dispatched[0].db_name,
                "root",
                dispatched[0].uuid,
                dispatched[0].seq,
                0,
                10,
                None,
                "done",
            )
            jobrunner.run_jobs()
        # round-robin continues on the next dispatch "ticks"
        self.assertEqual(
            [job.db_name for job in dispatched], ["db_a", "db_b", "db_a", "db_b"]
        )

    def test_round_robin_empty_channel_manager(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        self._new_channel_manager(
            jobrunner, "db_a", [ChannelConfig("root", 3)], pending_jobs=1
        )
        self._new_channel_manager(
            jobrunner, "db_b", [ChannelConfig("root", 3)], pending_jobs=3
        )
        dispatched = []
        with mock.patch.object(
            jobrunner, "_dispatch_job", side_effect=lambda job: dispatched.append(job)
        ):
            jobrunner.run_jobs()
        # round-robin continues with the only channel manager still having pending jobs
        self.assertEqual([job.db_name for job in dispatched], ["db_a", "db_b", "db_b"])

    def test_build_channel_manager_root_db_max_capacity(self):
        jobrunner = runner.QueueJobRunner(max_capacity=10)
        db = self._mock_db("db_a", [])
        channel_manager = jobrunner._build_channel_manager(db)
        root = channel_manager.get_channel_by_name("root")
        # the root channels inherits the global max capacity
        self.assertEqual(root.capacity, 10)

    def test_build_channel_manager_db_max_zero(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3, db_max_capacity="db_a:0,*:5")
        db = self._mock_db("db_a", [ChannelConfig("root", 5)])
        channel_manager = jobrunner._build_channel_manager(db)
        root = channel_manager.get_channel_by_name("root")
        # when db max capacity is at 0, the root channel of the channel manager
        # is considered paused
        self.assertTrue(root.paused)

    def test_build_channel_manager_db_max_negative(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3, db_max_capacity="db_a:-1,*:5")
        db = self._mock_db("db_a", [ChannelConfig("root", 5)])
        channel_manager = jobrunner._build_channel_manager(db)
        root = channel_manager.get_channel_by_name("root")
        # negative value is handled as 0, which is paused
        self.assertTrue(root.paused)

    def test_build_channel_manager_root_capacity_db(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3, db_max_capacity="*:2")
        db = self._mock_db("db_a", [ChannelConfig("root", 20)])
        channel_manager = jobrunner._build_channel_manager(db)
        root = channel_manager.get_channel_by_name("root")
        # the root channel is set to the db max capacity
        self.assertEqual(root.capacity, 2)

    @mute_logger("odoo.addons.queue_job.jobrunner.runner")
    def test_build_channel_manager_schema_error(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        # when the database schema has no columns, None is returned as channels config
        db = self._mock_db("db_a", None)
        channel_manager = jobrunner._build_channel_manager(db)
        root = channel_manager.get_channel_by_name("root")
        self.assertEqual(root.capacity, 0)
        self.assertTrue(root.paused)

    def test_build_channel_manager_handle_missing_root(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        # the configuration does not have root
        db = self._mock_db("db_a", [ChannelConfig("sub", 2)])
        channel_manager = jobrunner._build_channel_manager(db)
        # does not raise, "root" is automatically added
        root = channel_manager.get_channel_by_name("root", autocreate=False)
        self.assertEqual(root.capacity, 3)

    def test_register_db_server_wide(self):
        jobrunner = runner.QueueJobRunner(channel_config_string="root:3")
        global_manager = jobrunner._server_wide_channel_manager
        db = self._mock_db("db_a", None)
        jobrunner._register_db_server_wide(db)

        self.assertEqual(len(jobrunner._channel_managers), 1)
        self.assertEqual(jobrunner._channel_managers, [global_manager])
        self.assertEqual(jobrunner._channel_manager_by_db[db.db_name], global_manager)

    def test_max_capacity_zero_no_dispatch(self):
        jobrunner = runner.QueueJobRunner(max_capacity=0)
        self._new_channel_manager(
            jobrunner, "db_a", [ChannelConfig("root", 10)], pending_jobs=4
        )
        self._new_channel_manager(
            jobrunner, "db_b", [ChannelConfig("root", 10)], pending_jobs=4
        )
        with mock.patch.object(jobrunner, "_dispatch_job") as dispatch:
            jobrunner.run_jobs()
        dispatch.assert_not_called()

    def test_max_capacity_unconfigured_defaults_to_one(self):
        jobrunner = runner.QueueJobRunner()
        self.assertEqual(jobrunner.max_capacity, 1)
        self._new_channel_manager(
            jobrunner, "db_a", [ChannelConfig("root", 10)], pending_jobs=4
        )
        self._new_channel_manager(
            jobrunner, "db_b", [ChannelConfig("root", 10)], pending_jobs=4
        )
        with mock.patch.object(jobrunner, "_dispatch_job") as dispatch:
            jobrunner.run_jobs()
        self.assertEqual(dispatch.call_count, 1)

    def test_notify_reload(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        db = self._mock_db("db_a", [])
        db.conn.notifies = [mock.Mock(payload=runner.RELOAD_PAYLOAD)]
        jobrunner.db_by_name = {"db_a": db}

        with mock.patch.object(jobrunner, "_configure_db") as reconfigure:
            jobrunner.process_notifications()
        reconfigure.assert_called_once_with(db)

    def test_notify_reload_ignored_with_server_wide_channels(self):
        jobrunner = runner.QueueJobRunner(channel_config_string="root:3")
        db = self._mock_db("db_a", [])
        db.conn.notifies = [mock.Mock(payload=runner.RELOAD_PAYLOAD)]
        jobrunner.db_by_name = {"db_a": db}
        jobrunner._channel_manager_by_db = {"db_a": mock.MagicMock()}
        with mock.patch.object(jobrunner, "_configure_db") as reconfigure:
            jobrunner.process_notifications()
        reconfigure.assert_not_called()

    def test_notify_job_started(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        db = self._mock_db("db_a", None)
        channel_manager = ChannelManager()
        channel_manager.configure([ChannelConfig("root", 3)])
        jobrunner.db_by_name = {"db_a": db}
        self._register_channel_manager(jobrunner, "db_a", channel_manager)

        db.conn.notifies = [mock.Mock(payload="job-1")]
        # channel, uuid, seq, date_created, priority, eta, state
        job_row = ("root", "job-1", 0, 0, 10, None, "started")
        db.select_jobs.return_value.__enter__.return_value.fetchone.return_value = (
            job_row
        )

        jobrunner.process_notifications()

        db.select_jobs.assert_called_once_with("uuid = %s", ("job-1",))
        # the channel manager now counts the job as a running job
        self.assertEqual(channel_manager.running_count, 1)

    @mute_logger("odoo.addons.queue_job.jobrunner.runner")
    def test_build_channel_manager_invalid_configuration(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        db = self._mock_db("db_a", [ChannelConfig("root", 2, sequential=True)])

        channel_manager = jobrunner._build_channel_manager(db)

        root = channel_manager.get_channel_by_name("root")
        self.assertTrue(root.paused)

    def test_notify_existing_jobs(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        db = self._mock_db("db_a", [ChannelConfig("root", 3)])
        # channel, uuid, seq, date_created, priority, eta, state
        job_row = ("root", "db_a-job1", 0, 0, 10, None, "pending")
        db.select_jobs.return_value.__enter__.return_value = [job_row]

        jobrunner.db_by_name = {"db_a": db}

        channel_manager = jobrunner._build_channel_manager(db)
        self._register_channel_manager(jobrunner, "db_a", channel_manager)

        jobrunner._notify_existing_jobs(db, channel_manager)

        db.select_jobs.assert_called_once_with("state in %s", (runner.NOT_DONE,))
        pending_jobs = list(channel_manager.get_jobs_to_run(0))
        self.assertEqual([job.uuid for job in pending_jobs], ["db_a-job1"])

    def test_close_databases_reset_state(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        channel_manager = self._new_channel_manager(
            jobrunner, "db_a", [ChannelConfig("root", 3)], pending_jobs=1
        )
        db = jobrunner.db_by_name["db_a"]

        jobrunner.close_databases()

        self.assertEqual(list(channel_manager.get_jobs_to_run(0)), [])
        db.close.assert_called_once()
        self.assertEqual(jobrunner.db_by_name, {})
        self.assertEqual(jobrunner._channel_manager_by_db, {})
        self.assertEqual(jobrunner._channel_managers, [])

    def test_close_databases_remove_jobs_false(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        channel_manager = self._new_channel_manager(
            jobrunner, "db_a", [ChannelConfig("root", 3)], pending_jobs=1
        )

        jobrunner.close_databases(remove_jobs=False)

        # job is kept when remove_jobs=False
        self.assertEqual(len(list(channel_manager.get_jobs_to_run(0))), 1)

    def test_next_wakeup_time_no_channel_managers(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        self.assertEqual(jobrunner.next_wakeup_time(), 0)

    def test_next_wakeup_time_one_db_with_eta(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        channel_manager = self._new_channel_manager(
            jobrunner, "db_a", [ChannelConfig("root", 3)]
        )
        channel_manager.notify("db_a", "root", "db_a-0", 0, 0, 10, 500, "pending")
        self.assertEqual(jobrunner.next_wakeup_time(), 500)

    def test_next_wakeup_time_several_db(self):
        jobrunner = runner.QueueJobRunner(max_capacity=3)
        channel_manager_a = self._new_channel_manager(
            jobrunner, "db_a", [ChannelConfig("root", 3)]
        )
        channel_manager_b = self._new_channel_manager(
            jobrunner, "db_b", [ChannelConfig("root", 3)]
        )
        channel_manager_c = self._new_channel_manager(
            jobrunner, "db_c", [ChannelConfig("root", 3)]
        )
        # channel, uuid, seq, date_created, priority, eta, state
        channel_manager_a.notify("db_a", "root", "db_a-0", 0, 0, 10, 500, "pending")
        channel_manager_b.notify("db_b", "root", "db_b-0", 0, 0, 10, 200, "pending")
        channel_manager_c.notify("db_c", "root", "db_b-0", 0, 0, 10, 0, "pending")
        self.assertEqual(jobrunner.next_wakeup_time(), 200)
