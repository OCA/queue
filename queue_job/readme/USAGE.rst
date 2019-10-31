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

Tips and tricks
~~~~~~~~~~~~~~~

* **Idempotency** (https://www.restapitutorial.com/lessons/idempotency.html): The queue_job should be idempotent so they can be retried several times without impact on the data.
* **The job should test at the very beginning its relevance**: the moment the job will be executed is unknown by design. So the first task of a job should be to check if the related work is still relevant at the moment of the execution.

Patterns
~~~~~~~~
Through the time, two main patterns emerged:

1. For data exposed to users, a model should store the data and the model should be the creator of the job. The job is kept hidden from the users
2. For technical data, that are not exposed to the users, it is generally alright to create directly jobs with data passed as arguments to the job, without intermediary models.
