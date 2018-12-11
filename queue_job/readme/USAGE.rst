To use this module, you need to:

#. Go to ``Job Queue`` menu

Developers
~~~~~~~~~~

**Bypass jobs on running Odoo**

When you are developing (ie: connector modules) you might want
to bypass the queue job and run your code immediately.

To do so you can set `TEST_QUEUE_JOB_NO_DELAY=1` in your enviroment.

**Bypass jobs in tests**

When writing tests on job-related methods is always tricky to deal with
delayed recordsets. To make your testing life easier
you can set `test_queue_job_no_delay=True` in the context.

Tip: you can do this at test case level like this

.. code-block:: python

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(
            cls.env.context,
            test_queue_job_no_delay=True,  # no jobs thanks
        ))

Then all your tests execute the job methods synchronously
without delaying any jobs.
