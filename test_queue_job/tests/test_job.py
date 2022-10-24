# Copyright 2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import hashlib
from datetime import datetime, timedelta
from unittest import mock

import odoo.tests.common as common

from odoo.addons.queue_job import identity_exact
from odoo.addons.queue_job.delay import DelayableGraph
from odoo.addons.queue_job.exception import (
    FailedJobError,
    NoSuchJobError,
    RetryableJobError,
)
from odoo.addons.queue_job.job import (
    DONE,
    ENQUEUED,
    FAILED,
    PENDING,
    RETRY_INTERVAL,
    STARTED,
    WAIT_DEPENDENCIES,
    Job,
)

from .common import JobCommonCase


class TestJobsOnTestingMethod(JobCommonCase):
    """Test Job"""

    def test_new_job(self):
        """
        Create a job
        """
        test_job = Job(self.method)
        self.assertEqual(test_job.func.__func__, self.method.__func__)

    def test_eta(self):
        """When an `eta` is datetime, it uses it"""
        now = datetime.now()
        method = self.env["res.users"].mapped
        job_a = Job(method, eta=now)
        self.assertEqual(job_a.eta, now)

    def test_eta_integer(self):
        """When an `eta` is an integer, it adds n seconds up to now"""
        datetime_path = "odoo.addons.queue_job.job.datetime"
        with mock.patch(datetime_path, autospec=True) as mock_datetime:
            mock_datetime.now.return_value = datetime(2015, 3, 15, 16, 41, 0)
            job_a = Job(self.method, eta=60)
            self.assertEqual(job_a.eta, datetime(2015, 3, 15, 16, 42, 0))

    def test_eta_timedelta(self):
        """When an `eta` is a timedelta, it adds it up to now"""
        datetime_path = "odoo.addons.queue_job.job.datetime"
        with mock.patch(datetime_path, autospec=True) as mock_datetime:
            mock_datetime.now.return_value = datetime(2015, 3, 15, 16, 41, 0)
            delta = timedelta(hours=3)
            job_a = Job(self.method, eta=delta)
            self.assertEqual(job_a.eta, datetime(2015, 3, 15, 19, 41, 0))

    def test_perform_args(self):
        test_job = Job(self.method, args=("o", "k"), kwargs={"c": "!"})
        result = test_job.perform()
        self.assertEqual(result, (("o", "k"), {"c": "!"}))

    def test_retryable_error(self):
        test_job = Job(self.method, kwargs={"raise_retry": True}, max_retries=3)
        self.assertEqual(test_job.retry, 0)
        with self.assertRaises(RetryableJobError):
            test_job.perform()
        self.assertEqual(test_job.retry, 1)
        with self.assertRaises(RetryableJobError):
            test_job.perform()
        self.assertEqual(test_job.retry, 2)
        with self.assertRaises(FailedJobError):
            test_job.perform()
        self.assertEqual(test_job.retry, 3)

    def test_infinite_retryable_error(self):
        test_job = Job(self.method, kwargs={"raise_retry": True}, max_retries=0)
        self.assertEqual(test_job.retry, 0)
        with self.assertRaises(RetryableJobError):
            test_job.perform()
        self.assertEqual(test_job.retry, 1)

    def test_on_instance_method(self):
        class A(object):
            def method(self):
                pass

        with self.assertRaises(TypeError):
            Job(A.method)

    def test_on_model_method(self):
        job_ = Job(self.env["test.queue.job"].testing_method)
        self.assertEqual(job_.model_name, "test.queue.job")
        self.assertEqual(job_.method_name, "testing_method")

    def test_invalid_function(self):
        with self.assertRaises(TypeError):
            Job(1)

    def test_set_pending(self):
        job_a = Job(self.method)
        job_a.set_pending(result="test")
        self.assertEqual(job_a.state, PENDING)
        self.assertFalse(job_a.date_enqueued)
        self.assertFalse(job_a.date_started)
        self.assertEqual(job_a.retry, 0)
        self.assertEqual(job_a.result, "test")

    def test_set_enqueued(self):
        job_a = Job(self.method)
        datetime_path = "odoo.addons.queue_job.job.datetime"
        with mock.patch(datetime_path, autospec=True) as mock_datetime:
            mock_datetime.now.return_value = datetime(2015, 3, 15, 16, 41, 0)
            job_a.set_enqueued()

        self.assertEqual(job_a.state, ENQUEUED)
        self.assertEqual(job_a.date_enqueued, datetime(2015, 3, 15, 16, 41, 0))
        self.assertFalse(job_a.date_started)

    def test_set_started(self):
        job_a = Job(self.method)
        datetime_path = "odoo.addons.queue_job.job.datetime"
        with mock.patch(datetime_path, autospec=True) as mock_datetime:
            mock_datetime.now.return_value = datetime(2015, 3, 15, 16, 41, 0)
            job_a.set_started()

        self.assertEqual(job_a.state, STARTED)
        self.assertEqual(job_a.date_started, datetime(2015, 3, 15, 16, 41, 0))

    def test_worker_pid(self):
        """When a job is started, it gets the PID of the worker that starts it"""
        method = self.env["res.users"].mapped
        job_a = Job(method)
        self.assertFalse(job_a.worker_pid)
        with mock.patch("os.getpid", autospec=True) as mock_getpid:
            mock_getpid.return_value = 99999
            job_a.set_started()
            self.assertEqual(job_a.worker_pid, 99999)

        # reset the pid
        job_a.set_pending()
        self.assertFalse(job_a.worker_pid)

    def test_set_done(self):
        job_a = Job(self.method)
        job_a.date_started = datetime(2015, 3, 15, 16, 40, 0)
        datetime_path = "odoo.addons.queue_job.job.datetime"
        with mock.patch(datetime_path, autospec=True) as mock_datetime:
            mock_datetime.now.return_value = datetime(2015, 3, 15, 16, 41, 0)
            job_a.set_done(result="test")

        self.assertEqual(job_a.state, DONE)
        self.assertEqual(job_a.result, "test")
        self.assertEqual(job_a.date_done, datetime(2015, 3, 15, 16, 41, 0))
        self.assertEqual(job_a.exec_time, 60.0)
        self.assertFalse(job_a.exc_info)

    def test_set_failed(self):
        job_a = Job(self.method)
        job_a.set_failed(
            exc_info="failed test",
            exc_name="FailedTest",
            exc_message="Sadly this job failed",
        )
        self.assertEqual(job_a.state, FAILED)
        self.assertEqual(job_a.exc_info, "failed test")
        self.assertEqual(job_a.exc_name, "FailedTest")
        self.assertEqual(job_a.exc_message, "Sadly this job failed")

    def test_postpone(self):
        job_a = Job(self.method)
        datetime_path = "odoo.addons.queue_job.job.datetime"
        with mock.patch(datetime_path, autospec=True) as mock_datetime:
            mock_datetime.now.return_value = datetime(2015, 3, 15, 16, 41, 0)
            job_a.postpone(result="test", seconds=60)

        self.assertEqual(job_a.eta, datetime(2015, 3, 15, 16, 42, 0))
        self.assertEqual(job_a.result, "test")
        self.assertFalse(job_a.exc_info)

    def test_store(self):
        test_job = Job(self.method)
        test_job.store()
        stored = self.queue_job.search([("uuid", "=", test_job.uuid)])
        self.assertEqual(len(stored), 1)

    def test_store_extra_data(self):
        test_job = Job(self.method)
        test_job.store()
        stored = self.queue_job.search([("uuid", "=", test_job.uuid)])
        self.assertEqual(stored.additional_info, "JUST_TESTING")
        test_job.set_failed(exc_info="failed test", exc_name="FailedTest")
        test_job.store()
        stored.invalidate_cache()
        self.assertEqual(stored.additional_info, "JUST_TESTING_BUT_FAILED")

    def test_read(self):
        eta = datetime.now() + timedelta(hours=5)
        test_job = Job(
            self.method,
            args=("o", "k"),
            kwargs={"c": "!"},
            priority=15,
            eta=eta,
            description="My description",
        )
        test_job.worker_pid = 99999  # normally set on "set_start"
        test_job.company_id = self.env.ref("base.main_company").id
        test_job.store()
        job_read = Job.load(self.env, test_job.uuid)
        self.assertEqual(test_job.uuid, job_read.uuid)
        self.assertEqual(test_job.model_name, job_read.model_name)
        self.assertEqual(test_job.func.__func__, job_read.func.__func__)
        self.assertEqual(test_job.args, job_read.args)
        self.assertEqual(test_job.kwargs, job_read.kwargs)
        self.assertEqual(test_job.method_name, job_read.method_name)
        self.assertEqual(test_job.description, job_read.description)
        self.assertEqual(test_job.state, job_read.state)
        self.assertEqual(test_job.priority, job_read.priority)
        self.assertEqual(test_job.exc_info, job_read.exc_info)
        self.assertEqual(test_job.result, job_read.result)
        self.assertEqual(test_job.user_id, job_read.user_id)
        self.assertEqual(test_job.company_id, job_read.company_id)
        self.assertEqual(test_job.worker_pid, 99999)
        delta = timedelta(seconds=1)  # DB does not keep milliseconds
        self.assertAlmostEqual(
            test_job.date_created, job_read.date_created, delta=delta
        )
        self.assertAlmostEqual(
            test_job.date_started, job_read.date_started, delta=delta
        )
        self.assertAlmostEqual(
            test_job.date_enqueued, job_read.date_enqueued, delta=delta
        )
        self.assertAlmostEqual(test_job.date_done, job_read.date_done, delta=delta)
        self.assertAlmostEqual(test_job.eta, job_read.eta, delta=delta)

        test_date = datetime(2015, 3, 15, 21, 7, 0)
        job_read.date_enqueued = test_date
        job_read.date_started = test_date
        job_read.date_done = test_date
        job_read.store()

        job_read = Job.load(self.env, test_job.uuid)
        self.assertAlmostEqual(job_read.date_started, test_date, delta=delta)
        self.assertAlmostEqual(job_read.date_enqueued, test_date, delta=delta)
        self.assertAlmostEqual(job_read.date_done, test_date, delta=delta)
        self.assertAlmostEqual(job_read.exec_time, 0.0)

    def test_job_unlinked(self):
        test_job = Job(self.method, args=("o", "k"), kwargs={"c": "!"})
        test_job.store()
        stored = self.queue_job.search([("uuid", "=", test_job.uuid)])
        stored.unlink()
        with self.assertRaises(NoSuchJobError):
            Job.load(self.env, test_job.uuid)

    def test_unicode(self):
        test_job = Job(
            self.method,
            args=("öô¿‽", "ñě"),
            kwargs={"c": "ßø"},
            priority=15,
            description="My dé^Wdescription",
        )
        test_job.store()
        job_read = Job.load(self.env, test_job.uuid)
        self.assertEqual(test_job.args, job_read.args)
        self.assertEqual(job_read.args, ("öô¿‽", "ñě"))
        self.assertEqual(test_job.kwargs, job_read.kwargs)
        self.assertEqual(job_read.kwargs, {"c": "ßø"})
        self.assertEqual(test_job.description, job_read.description)
        self.assertEqual(job_read.description, "My dé^Wdescription")

    def test_accented_bytestring(self):
        test_job = Job(
            self.method,
            args=("öô¿‽", "ñě"),
            kwargs={"c": "ßø"},
            priority=15,
            description="My dé^Wdescription",
        )
        test_job.store()
        job_read = Job.load(self.env, test_job.uuid)
        self.assertEqual(job_read.args, ("öô¿‽", "ñě"))
        self.assertEqual(job_read.kwargs, {"c": "ßø"})
        self.assertEqual(job_read.description, "My dé^Wdescription")

    def test_job_delay(self):
        self.cr.execute("delete from queue_job")
        job_ = self.env["test.queue.job"].with_delay().testing_method()
        stored = self.queue_job.search([])
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored.uuid, job_.uuid, "Incorrect returned Job UUID")

    def test_job_delay_model_method(self):
        self.cr.execute("delete from queue_job")
        delayable = self.env["test.queue.job"].with_delay()
        job_instance = delayable.testing_method("a", k=1)
        self.assertTrue(job_instance)
        result = job_instance.perform()
        self.assertEqual(result, (("a",), {"k": 1}))

    def test_job_identity_key_str(self):
        id_key = "e294e8444453b09d59bdb6efbfec1323"
        test_job_1 = Job(
            self.method,
            priority=15,
            description="Test I am the first one",
            identity_key=id_key,
        )
        test_job_1.store()
        job1 = Job.load(self.env, test_job_1.uuid)
        self.assertEqual(job1.identity_key, id_key)

    def test_job_identity_key_func_exact(self):
        hasher = hashlib.sha1()
        hasher.update(b"test.queue.job")
        hasher.update(b"testing_method")
        hasher.update(str(sorted([])).encode("utf-8"))
        hasher.update(str((1, "foo")).encode("utf-8"))
        hasher.update(str(sorted({"bar": "baz"}.items())).encode("utf-8"))
        expected_key = hasher.hexdigest()

        test_job_1 = Job(
            self.method,
            args=[1, "foo"],
            kwargs={"bar": "baz"},
            identity_key=identity_exact,
        )
        self.assertEqual(test_job_1.identity_key, expected_key)
        test_job_1.store()

        job1 = Job.load(self.env, test_job_1.uuid)
        self.assertEqual(job1.identity_key, expected_key)


class TestJobs(JobCommonCase):
    """Test jobs on other methods or with different job configuration"""

    def test_description(self):
        """If no description is given to the job, it
        should be computed from the function
        """
        # if a docstring is defined for the function
        # it's used as description
        job_a = Job(self.env["test.queue.job"].testing_method)
        self.assertEqual(job_a.description, "Method used for tests")
        # if no docstring, the description is computed
        job_b = Job(self.env["test.queue.job"].no_description)
        self.assertEqual(job_b.description, "test.queue.job.no_description")
        # case when we explicitly specify the description
        description = "My description"
        job_a = Job(self.env["test.queue.job"].testing_method, description=description)
        self.assertEqual(job_a.description, description)

    def test_retry_pattern(self):
        """When we specify a retry pattern, the eta must follow it"""
        datetime_path = "odoo.addons.queue_job.job.datetime"
        method = self.env["test.queue.job"].job_with_retry_pattern
        with mock.patch(datetime_path, autospec=True) as mock_datetime:
            mock_datetime.now.return_value = datetime(2015, 6, 1, 15, 10, 0)
            test_job = Job(method, max_retries=0)
            test_job.retry += 1
            test_job.postpone(self.env)
            self.assertEqual(test_job.retry, 1)
            self.assertEqual(test_job.eta, datetime(2015, 6, 1, 15, 11, 0))
            test_job.retry += 1
            test_job.postpone(self.env)
            self.assertEqual(test_job.retry, 2)
            self.assertEqual(test_job.eta, datetime(2015, 6, 1, 15, 13, 0))
            test_job.retry += 1
            test_job.postpone(self.env)
            self.assertEqual(test_job.retry, 3)
            self.assertEqual(test_job.eta, datetime(2015, 6, 1, 15, 10, 10))
            test_job.retry += 1
            test_job.postpone(self.env)
            self.assertEqual(test_job.retry, 4)
            self.assertEqual(test_job.eta, datetime(2015, 6, 1, 15, 10, 10))
            test_job.retry += 1
            test_job.postpone(self.env)
            self.assertEqual(test_job.retry, 5)
            self.assertEqual(test_job.eta, datetime(2015, 6, 1, 15, 15, 0))

    def test_retry_pattern_no_zero(self):
        """When we specify a retry pattern without 0, uses RETRY_INTERVAL"""
        method = self.env["test.queue.job"].job_with_retry_pattern__no_zero
        test_job = Job(method, max_retries=0)
        test_job.retry += 1
        self.assertEqual(test_job.retry, 1)
        self.assertEqual(test_job._get_retry_seconds(), RETRY_INTERVAL)
        test_job.retry += 1
        self.assertEqual(test_job.retry, 2)
        self.assertEqual(test_job._get_retry_seconds(), RETRY_INTERVAL)
        test_job.retry += 1
        self.assertEqual(test_job.retry, 3)
        self.assertEqual(test_job._get_retry_seconds(), 180)
        test_job.retry += 1
        self.assertEqual(test_job.retry, 4)
        self.assertEqual(test_job._get_retry_seconds(), 180)

    def test_job_delay_model_method_multi(self):
        rec1 = self.env["test.queue.job"].create({"name": "test1"})
        rec2 = self.env["test.queue.job"].create({"name": "test2"})
        recs = rec1 + rec2
        job_instance = recs.with_delay().mapped("name")
        self.assertTrue(job_instance)
        self.assertEqual(job_instance.args, ("name",))
        self.assertEqual(job_instance.recordset, recs)
        self.assertEqual(job_instance.model_name, "test.queue.job")
        self.assertEqual(job_instance.method_name, "mapped")
        self.assertEqual(["test1", "test2"], job_instance.perform())

    def test_job_identity_key_no_duplicate(self):
        """If a job with same identity key in queue do not add a new one"""
        id_key = "e294e8444453b09d59bdb6efbfec1323"
        rec1 = self.env["test.queue.job"].create({"name": "test1"})
        job_1 = rec1.with_delay(identity_key=id_key).mapped("name")

        self.assertTrue(job_1)
        job_2 = rec1.with_delay(identity_key=id_key).mapped("name")
        self.assertEqual(job_2.uuid, job_1.uuid)

    def test_job_with_mutable_arguments(self):
        """Job with mutable arguments do not mutate on perform()"""
        delayable = self.env["test.queue.job"].with_delay()
        job_instance = delayable.job_alter_mutable([1], mutable_kwarg={"a": 1})
        self.assertTrue(job_instance)
        result = job_instance.perform()
        self.assertEqual(result, ([1, 2], {"a": 1, "b": 2}))
        job_instance.set_done()
        # at this point, the 'args' and 'kwargs' of the job instance
        # might have been modified, but they must never be modified in
        # the queue_job table after their creation, so a new 'load' will
        # get the initial values.
        job_instance.store()
        # jobs are always loaded before being performed, so we simulate
        # this behavior here to check if we have the correct initial arguments
        job_instance = Job.load(self.env, job_instance.uuid)
        self.assertEqual(([1],), job_instance.args)
        self.assertEqual({"mutable_kwarg": {"a": 1}}, job_instance.kwargs)

    def test_store_env_su_no_sudo(self):
        demo_user = self.env.ref("base.user_demo")
        self.env = self.env(user=demo_user)
        delayable = self.env["test.queue.job"].with_delay()
        test_job = delayable.testing_method()
        stored = test_job.db_record()
        job_instance = Job.load(self.env, stored.uuid)
        self.assertFalse(job_instance.recordset.env.su)
        self.assertTrue(job_instance.user_id, demo_user)

    def test_store_env_su_sudo(self):
        demo_user = self.env.ref("base.user_demo")
        self.env = self.env(user=demo_user)
        delayable = self.env["test.queue.job"].sudo().with_delay()
        test_job = delayable.testing_method()
        stored = test_job.db_record()
        job_instance = Job.load(self.env, stored.uuid)
        self.assertTrue(job_instance.recordset.env.su)
        self.assertTrue(job_instance.user_id, demo_user)


class TestJobModel(JobCommonCase):
    def test_job_change_state(self):
        stored = self._create_job()
        stored._change_job_state(DONE, result="test")
        self.assertEqual(stored.state, DONE)
        self.assertEqual(stored.result, "test")
        stored._change_job_state(PENDING, result="test2")
        self.assertEqual(stored.state, PENDING)
        self.assertEqual(stored.result, "test2")
        with self.assertRaises(ValueError):
            # only PENDING and DONE supported
            stored._change_job_state(STARTED)

    def test_button_done(self):
        stored = self._create_job()
        stored.button_done()
        self.assertEqual(stored.state, DONE)
        self.assertEqual(
            stored.result, "Manually set to done by %s" % self.env.user.name
        )

    def test_requeue(self):
        stored = self._create_job()
        stored.write({"state": "failed"})
        stored.requeue()
        self.assertEqual(stored.state, PENDING)

    def test_requeue_wait_dependencies_not_touched(self):
        job_root = Job(self.env["test.queue.job"].testing_method)
        job_child = Job(self.env["test.queue.job"].testing_method)
        job_child.add_depends({job_root})
        job_root.store()
        job_child.store()

        DelayableGraph._ensure_same_graph_uuid([job_root, job_child])

        record_root = job_root.db_record()
        record_child = job_child.db_record()
        self.assertEqual(record_root.state, PENDING)
        self.assertEqual(record_child.state, WAIT_DEPENDENCIES)
        record_root.write({"state": "failed"})

        (record_root + record_child).requeue()
        self.assertEqual(record_root.state, PENDING)
        self.assertEqual(record_child.state, WAIT_DEPENDENCIES)

    def test_message_when_write_fail(self):
        stored = self._create_job()
        stored.write({"state": "failed"})
        self.assertEqual(stored.state, FAILED)
        messages = stored.message_ids
        self.assertEqual(len(messages), 1)

    def test_follower_when_write_fail(self):
        """Check that inactive users doesn't are not followers even if
        they are linked to an active partner"""
        group = self.env.ref("queue_job.group_queue_job_manager")
        vals = {
            "name": "xx",
            "login": "xx",
            "groups_id": [(6, 0, [group.id])],
            "active": False,
        }
        inactiveusr = self.user.create(vals)
        inactiveusr.partner_id.active = True
        self.assertFalse(inactiveusr in group.users)
        stored = self._create_job()
        stored.write({"state": "failed"})
        followers = stored.message_follower_ids.mapped("partner_id")
        self.assertFalse(inactiveusr.partner_id in followers)
        self.assertFalse({u.partner_id for u in group.users} - set(followers))

    def test_wizard_requeue(self):
        stored = self._create_job()
        stored.write({"state": "failed"})
        model = self.env["queue.requeue.job"]
        model = model.with_context(active_model="queue.job", active_ids=stored.ids)
        model.create({}).requeue()
        self.assertEqual(stored.state, PENDING)

    def test_context_uuid(self):
        delayable = self.env["test.queue.job"].with_delay()
        test_job = delayable.testing_method(return_context=True)
        result = test_job.perform()
        key_present = "job_uuid" in result
        self.assertTrue(key_present)
        self.assertEqual(result["job_uuid"], test_job._uuid)

    def test_override_channel(self):
        delayable = self.env["test.queue.job"].with_delay(channel="root.sub.sub")
        test_job = delayable.testing_method(return_context=True)
        self.assertEqual("root.sub.sub", test_job.channel)

    def test_job_change_user_id(self):
        demo_user = self.env.ref("base.user_demo")
        stored = self._create_job()
        stored.user_id = demo_user
        self.assertEqual(stored.records.env.uid, demo_user.id)


class TestJobStorageMultiCompany(common.TransactionCase):
    """Test storage of jobs"""

    def setUp(self):
        super(TestJobStorageMultiCompany, self).setUp()
        self.queue_job = self.env["queue.job"]
        grp_queue_job_manager = self.ref("queue_job.group_queue_job_manager")
        User = self.env["res.users"]
        Company = self.env["res.company"]
        Partner = self.env["res.partner"]

        main_company = self.env.ref("base.main_company")

        self.partner_user = Partner.create(
            {"name": "Simple User", "email": "simple.user@example.com"}
        )
        self.simple_user = User.create(
            {
                "partner_id": self.partner_user.id,
                "company_ids": [(4, main_company.id)],
                "login": "simple_user",
                "name": "simple user",
                "groups_id": [],
            }
        )

        self.other_partner_a = Partner.create(
            {"name": "My Company a", "is_company": True, "email": "test@tes.ttest"}
        )
        self.other_company_a = Company.create(
            {
                "name": "My Company a",
                "partner_id": self.other_partner_a.id,
                "currency_id": self.ref("base.EUR"),
            }
        )
        self.other_user_a = User.create(
            {
                "partner_id": self.other_partner_a.id,
                "company_id": self.other_company_a.id,
                "company_ids": [(4, self.other_company_a.id)],
                "login": "my_login a",
                "name": "my user A",
                "groups_id": [(4, grp_queue_job_manager)],
            }
        )
        self.other_partner_b = Partner.create(
            {"name": "My Company b", "is_company": True, "email": "test@tes.ttest"}
        )
        self.other_company_b = Company.create(
            {
                "name": "My Company b",
                "partner_id": self.other_partner_b.id,
                "currency_id": self.ref("base.EUR"),
            }
        )
        self.other_user_b = User.create(
            {
                "partner_id": self.other_partner_b.id,
                "company_id": self.other_company_b.id,
                "company_ids": [(4, self.other_company_b.id)],
                "login": "my_login_b",
                "name": "my user B",
                "groups_id": [(4, grp_queue_job_manager)],
            }
        )

    def _create_job(self, env):
        self.cr.execute("delete from queue_job")
        env["test.queue.job"].with_delay().testing_method()
        stored = self.queue_job.search([])
        self.assertEqual(len(stored), 1)
        return stored

    def test_job_default_company_id(self):
        """the default company is the one from the current user_id"""
        stored = self._create_job(self.env)
        self.assertEqual(
            stored.company_id.id,
            self.ref("base.main_company"),
            "Incorrect default company_id",
        )
        env = self.env(user=self.other_user_b.id)
        stored = self._create_job(env)
        self.assertEqual(
            stored.company_id.id,
            self.other_company_b.id,
            "Incorrect default company_id",
        )

    def test_job_no_company_id(self):
        """if we put an empty company_id in the context
        jobs are created without company_id
        """
        env = self.env(context={"company_id": None})
        stored = self._create_job(env)
        self.assertFalse(stored.company_id, "Company_id should be empty")

    def test_job_specific_company_id(self):
        """If a company_id specified in the context
        it's used by default for the job creation"""
        env = self.env(context={"company_id": self.other_company_a.id})
        stored = self._create_job(env)
        self.assertEqual(
            stored.company_id.id, self.other_company_a.id, "Incorrect company_id"
        )

    def test_job_subscription(self):
        # if the job is created without company_id, all members of
        # queue_job.group_queue_job_manager must be followers
        User = self.env["res.users"]
        no_company_context = dict(self.env.context, company_id=None)
        no_company_env = self.env(user=self.simple_user, context=no_company_context)
        stored = self._create_job(no_company_env)
        stored._message_post_on_failure()
        users = (
            User.search(
                [("groups_id", "=", self.ref("queue_job.group_queue_job_manager"))]
            )
            + stored.user_id
        )
        self.assertEqual(len(stored.message_follower_ids), len(users))
        expected_partners = [u.partner_id for u in users]
        self.assertSetEqual(
            set(stored.message_follower_ids.mapped("partner_id")),
            set(expected_partners),
        )
        followers_id = stored.message_follower_ids.mapped("partner_id.id")
        self.assertIn(self.other_partner_a.id, followers_id)
        self.assertIn(self.other_partner_b.id, followers_id)
        # jobs created for a specific company_id are followed only by
        # company's members
        company_a_context = dict(self.env.context, company_id=self.other_company_a.id)
        company_a_env = self.env(user=self.simple_user, context=company_a_context)
        stored = self._create_job(company_a_env)
        stored.with_user(self.other_user_a.id)
        stored._message_post_on_failure()
        # 2 because simple_user (creator of job) + self.other_partner_a
        self.assertEqual(len(stored.message_follower_ids), 2)
        users = self.simple_user + self.other_user_a
        expected_partners = [u.partner_id for u in users]
        self.assertSetEqual(
            set(stored.message_follower_ids.mapped("partner_id")),
            set(expected_partners),
        )
        followers_id = stored.message_follower_ids.mapped("partner_id.id")
        self.assertIn(self.other_partner_a.id, followers_id)
        self.assertNotIn(self.other_partner_b.id, followers_id)
