# Copyright 2019 Camptocamp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from contextlib import contextmanager

import mock

from odoo.addons.queue_job.job import Job


class JobCounter:
    def __init__(self, env):
        super().__init__()
        self.env = env
        self.existing = self.search_all()

    def count_all(self):
        return len(self.search_all())

    def count_created(self):
        return len(self.search_created())

    def count_existing(self):
        return len(self.existing)

    def search_created(self):
        return self.search_all() - self.existing

    def search_all(self):
        return self.env["queue.job"].search([])


class JobMixin:
    def job_counter(self):
        return JobCounter(self.env)

    def perform_jobs(self, jobs):
        for job in jobs.search_created():
            Job.load(self.env, job.uuid).perform()


@contextmanager
def mock_with_delay():
    """Context Manager mocking ``with_delay()``

    Mocking this method means we can decorrelate the tests in:

    * the part that delay the job with the expected arguments
    * the execution of the job itself

    The first kind of test does not need to actually create the jobs in the
    database, as we can inspect how the Mocks were called.

    The second kind of test calls directly the method decorated by ``@job``
    with the arguments that we want to test.

    The context manager returns 2 mocks:
    * the first allow to check that with_delay() was called and with which
      arguments
    * the second to check which job method was called and with which arguments.

    Example of test::

        def test_export(self):
            with mock_with_delay() as (delayable_cls, delayable):
                # inside this method, there is a call
                # partner.with_delay(priority=15).export_record('test')
                self.record.run_export()

                # check 'with_delay()' part:
                self.assertEqual(delayable_cls.call_count, 1)
                # arguments passed in 'with_delay()'
                delay_args, delay_kwargs = delayable_cls.call_args
                self.assertEqual(
                    delay_args, (self.env['res.partner'],)
                )
                self.assertDictEqual(delay_kwargs, {priority: 15})

                # check what's passed to the job method 'export_record'
                self.assertEqual(delayable.export_record.call_count, 1)
                delay_args, delay_kwargs = delayable.export_record.call_args
                self.assertEqual(delay_args, ('test',))
                self.assertDictEqual(delay_kwargs, {})

    An example of the first kind of test:
    https://github.com/camptocamp/connector-jira/blob/0ca4261b3920d5e8c2ae4bb0fc352ea3f6e9d2cd/connector_jira/tests/test_batch_timestamp_import.py#L43-L76  # noqa
    And the second kind:
    https://github.com/camptocamp/connector-jira/blob/0ca4261b3920d5e8c2ae4bb0fc352ea3f6e9d2cd/connector_jira/tests/test_import_task.py#L34-L46  # noqa

    """
    with mock.patch(
        "odoo.addons.queue_job.models.base.DelayableRecordset",
        name="DelayableRecordset",
        spec=True,
    ) as delayable_cls:
        # prepare the mocks
        delayable = mock.MagicMock(name="DelayableBinding")
        delayable_cls.return_value = delayable
        yield delayable_cls, delayable
