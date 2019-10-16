* After creating a new database or installing ``queue_job`` on an
  existing database, Odoo must be restarted for the runner to detect it.

* When Odoo shuts down normally, it waits for running jobs to finish.
  However, when the Odoo server crashes or is otherwise force-stopped,
  running jobs are interrupted while the runner has no chance to know
  they have been aborted. In such situations, jobs may remain in
  ``started`` or ``enqueued`` state after the Odoo server is halted.
  Since the runner has no way to know if they are actually running or
  not, and does not know for sure if it is safe to restart the jobs,
  it does not attempt to restart them automatically. Such stale jobs
  therefore fill the running queue and prevent other jobs to start.
  You must therefore requeue them manually, either from the Jobs view,
  or by running the following SQL statement *before starting Odoo*:

.. code-block:: sql

  update queue_job set state='pending' where state in ('started', 'enqueued')

Tips and tricks
---------------

* **Idempotency** (https://www.restapitutorial.com/lessons/idempotency.html): The queue_job should be idempotent so they can be retried several times without impact on the data.
* **The job should test at the very beginning its relevance**: the moment the job will be executed is unknown by design. So the first task of a job should be to check if the related work is still relevant at the moment of the execution.

Patterns
~~~~~~~~
Through the time, two main patterns emerged:

1. For data exposed to users, a model should store the data and the model should be the creator of the job. The job is kept hidden from the users
2. For technical data, that are not exposed to the users, it is generally alright to create directly jobs with data passed as arguments to the job, without intermediary models.
