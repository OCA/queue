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

Odoo.sh configuration
~~~~~~~~~~~~~~~~~~~~~

When using odoo.sh, the configuration in ``.config/odoo/odoo.conf`` must include
(at least):


.. code-block::

   [options]
   server_wide_modules=web,queue_job

   [queue_job]
   host=<your-odoo-instance>.odoo.com
   scheme=https
   port=443

Example of host: ``myproject-main-1552740.dev.odoo.com``

.. note::
    Odoo.sh puts workers to sleep when they stop receiving HTTP requests.
    Jobs scheduled in the future or by a scheduled action could therefore not run.
    A workaround is to wake up the workers periodically using an external
    service (a simple GET on any URL served by Odoo is enough).
