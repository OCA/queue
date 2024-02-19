* Using environment variables and command line:

  * Adjust environment variables (optional):

    - ``ODOO_QUEUE_JOB_CHANNELS=root:4`` or any other channels configuration.
      The default is ``root:1``

    - if ``xmlrpc_port`` is not set: ``ODOO_QUEUE_JOB_PORT=8069``

  * Start Odoo with ``--load=web,queue_job``
    and ``--workers`` greater than 1. [1]_


* Using the Odoo configuration file:

.. code-block:: ini

  [options]
  (...)
  workers = 6
  server_wide_modules = web,queue_job

  (...)
  [queue_job]
  channels = root:2

* Confirm the runner is starting correctly by checking the odoo log file:

.. code-block::

  ...INFO...queue_job.jobrunner.runner: starting
  ...INFO...queue_job.jobrunner.runner: initializing database connections
  ...INFO...queue_job.jobrunner.runner: queue job runner ready for db <dbname>
  ...INFO...queue_job.jobrunner.runner: database connections ready

* Create jobs (eg using ``base_import_async``) and observe they
  start immediately and in parallel.

* Tip: to enable debug logging for the queue job, use
  ``--log-handler=odoo.addons.queue_job:DEBUG``

.. [1] It works with the threaded Odoo server too, although this way
       of running Odoo is obviously not for production purposes.

* Deploying in high availability mode or odoo.sh:

When deploying queue_job on multiple nodes or on odoo.sh, on top of the configuration
parameters mentioned above you need to also set the env variable
ODOO_QUEUE_JOB_HIGH_AVAILABILITY=1 or via config parameter as such:

.. code-block:: ini
  
  (...)
  [queue_job]
  high_availability = 1


> :warning: **Warning:** Failure to enable the high_availability flag on odoo.sh could
constitute a breach of Acceptable Use Policy. Always enable this flag via the odoo.conf file for odoo.sh
deployment
