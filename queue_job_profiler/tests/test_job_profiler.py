# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import exceptions, fields
from odoo.tests import common, new_test_user

from odoo.addons.queue_job_profiler.controllers.main import RunJobController


class TestJobFunction(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.user_func1 = cls.env["queue.job.function"].create(
            {"model_id": cls.env["ir.model"]._get_id("res.users"), "method": "read"}
        )
        cls.user_func2 = cls.env["queue.job.function"].create(
            {"model_id": cls.env["ir.model"]._get_id("res.users"), "method": "read"}
        )
        cls.user1 = new_test_user(cls.env, login="user1", groups="base.group_user")
        cls.user2 = new_test_user(cls.env, login="user2", groups="base.group_user")

    def test_func_constraint(self):
        with self.assertRaisesRegex(
            exceptions.ValidationError,
            "A profiling until date must be set when profiling is enabled.",
        ):
            self.user_func1.profiling_enabled = True

    def _enable_profiling(self, job_function, users=None, delta=timedelta(hours=1)):
        job_function.profiling_user_ids = users
        job_function.profiling_until = fields.Datetime.now() + delta
        job_function.profiling_enabled = True

    def test_func_profiling_enabled(self):
        # By default, profiling should be disabled for all users
        for user in (self.env.user, self.user1, self.user2):
            self.assertFalse(self.user_func1.with_user(user).is_profiling_enabled())
        # Enable for all users (no profiling users set)
        self._enable_profiling(self.user_func1)
        for user in (self.env.user, self.user1, self.user2):
            self.assertTrue(self.user_func1.with_user(user).is_profiling_enabled())
        # Enable it for user1 and user2
        self._enable_profiling(self.user_func1, users=self.user1 + self.user2)
        self.assertTrue(self.user_func1.with_user(self.user1).is_profiling_enabled())
        self.assertTrue(self.user_func1.with_user(self.user2).is_profiling_enabled())
        self.assertFalse(
            self.user_func1.with_user(self.env.user).is_profiling_enabled()
        )
        # Check for another job function and user
        self._enable_profiling(self.user_func2, users=self.user2)
        self.assertTrue(self.user_func2.with_user(self.user2).is_profiling_enabled())
        for user in (self.env.user, self.user1):
            self.assertFalse(self.user_func2.with_user(user).is_profiling_enabled())
        with freeze_time(fields.Datetime.now() + timedelta(days=1)):
            # After the profiling_until date, profiling should be disabled for all users
            for user in (self.env.user, self.user1, self.user2):
                self.assertFalse(self.user_func1.with_user(user).is_profiling_enabled())
                self.assertFalse(self.user_func2.with_user(user).is_profiling_enabled())

    def test_job_without_function(self):
        # if a job has no function, it cannot be profiled
        self.user_func1.sudo().unlink()
        self.user_func2.sudo().unlink()
        job1 = self.env.user.with_delay().read(["id"])
        job1.store()
        job_rec1 = job1.db_record()
        self.assertFalse(job_rec1.job_function_id)
        self.assertFalse(job_rec1.job_is_profiled)
        with self.assertRaises(ValueError):
            self.env["queue.job.function"]._profile_make_name(job_rec1)

    def test_job_is_profiled(self):
        job1 = self.env.user.with_delay().read(["id"])
        job1.store()
        job_rec1 = job1.db_record()
        job2 = self.env.user.with_delay().read(["id"])
        job2.store()
        job_rec2 = job2.db_record()
        jobs = job_rec1 | job_rec2
        self.assertEqual(jobs.mapped("job_is_profiled"), [False, False])
        profile_name1 = self.user_func1._profile_make_name(job_rec1)
        profile_name2 = self.user_func2._profile_make_name(job_rec2)
        prof1 = self.env["ir.profile"].create({"name": profile_name1})
        jobs.invalidate_recordset()
        self.assertEqual(jobs.mapped("job_is_profiled"), [True, False])
        prof2 = self.env["ir.profile"].create({"name": profile_name2})
        jobs.invalidate_recordset()
        self.assertEqual(jobs.mapped("job_is_profiled"), [True, True])
        self.assertEqual(job_rec1._profiler_get_record(profile_name1), prof1)
        self.assertEqual(job_rec2._profiler_get_record(profile_name2), prof2)

    def test_job_action_view_profile(self):
        job = self.env.user.with_delay().read(["id"])
        job.store()
        job_rec = job.db_record()
        self.assertEqual(
            job_rec.action_view_profile(), {"type": "ir.actions.act_window_close"}
        )
        profile_name = self.user_func1._profile_make_name(job_rec)
        prof = self.env["ir.profile"].create({"name": profile_name})
        action = job_rec.action_view_profile()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "ir.profile")
        self.assertEqual(action["res_id"], prof.id)

    def _run_controller(self, job, user=None):
        controller = RunJobController()
        env = self.env(user=user) if user else self.env
        with (
            patch.object(self.env.cr, "commit"),
        ):
            controller._try_perform_job(env, job)

    def test_controller(self):
        job = self.env.user.with_delay().read(["id"])
        self._enable_profiling(self.user_func1, [self.user1.id])
        # TODO @simahawk: I'd like to look for new `ir_profile` records
        # but somehow looks very hard to find them
        # since `Profiler` creates them in a separated db connection.
        # All my attempts to mock the cr or de connection of `db_connect`
        # failed poorly, so I prefer to not waste too much time aroudn this.
        # I'm falling back to patching the controller method
        # that should be called when profiling is enabled.
        # The profiler init is tested in another method below.
        # Not ideal, but better than no test :)
        with patch.object(RunJobController, "_profiler_get") as mock_profiler_get:
            self._run_controller(job)
            mock_profiler_get.assert_not_called()
        with patch.object(RunJobController, "_profiler_get") as mock_profiler_get:
            self._run_controller(job, user=self.user1)
            mock_profiler_get.assert_called_once()
        with freeze_time(fields.Datetime.now() + timedelta(days=1)):
            with patch.object(RunJobController, "_profiler_get") as mock_profiler_get:
                self._run_controller(job)
                mock_profiler_get.assert_not_called()

    def test_controller_profiler_get(self):
        # as we mocked it before, make sure it works
        controller = RunJobController()
        job = self.env.user.with_delay().read(["id"])
        profiler = controller._profiler_get(self.env, job)
        self.assertEqual(
            profiler.description, f"queue.job {job.uuid} - {job.job_function_name}"
        )
        self.assertEqual(
            profiler.profile_session, f"{self.env.user.name} (uid={self.env.user.id})"
        )
