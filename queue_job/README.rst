.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=========
Job Queue
=========

This addon adds an integrated Job Queue to Odoo.

It allows to postpone method calls executed asynchronously.

Jobs are executed in the background by a ``Jobrunner``, in their own transaction.

Example:

.. code-block:: python

  class MyModel(models.Model):
     _name = 'my.model'

     @api.multi
     @job
     def my_method(self, a, k=None):
         _logger.info('executed with a: %s and k: %s', a, k)


  class MyOtherModel(models.Model):
      _name = 'my.other.model'

      @api.multi
      def button_do_stuff(self):
          self.env['my.model'].with_delay().my_method('a', k=2)


In the snippet of code above, when we call ``button_do_stuff``, a job capturing
the method and arguments will be postponed.  It will be executed as soon as the
Jobrunner has a free bucket, which can be instantaneous if no other job is
running.


Features:
* Views for jobs, jobs are stored in PostgreSQL
* Jobrunner: execute the jobs, highly efficient thanks to PostgreSQL's NOTIFY
* Channels: give a capacity for the root channel and its sub-channels and
  segregate jobs in them. Allow for instance to restrict heavy jobs to be
  executed one at a time while little ones are executed 4 at a times.
* Retries: Ability to retry jobs by raising a type of exception
* Retry Pattern: the 3 first tries, retry after 10 seconds, the 5 next tries,
  retry after 1 minutes, ...
* Job properties: priorities, estimated time of arrival (ETA), custom
  description, number of retries
* Related Actions: link an action on the job view, such as open the record
  concerned by the job


Installation
============

Be sure to have the ``requests`` library.

Configuration
=============

* Using environment variables and command line:

 * Adjust environment variables (optional):

  - ``ODOO_QUEUE_JOB_CHANNELS=root:4``

   - or any other channels configuration. The default is ``root:1``

  - if ``xmlrpc_port`` is not set: ``ODOO_QUEUE_JOB_PORT=8069``

 * Start Odoo with ``--load=web,web_kanban,queue_job``
   and ``--workers`` greater than 1. [1]_


* Using the Odoo configuration file:

.. code-block:: ini

  [options]
  (...)
  workers = 4
  server_wide_modules = web,web_kanban,queue_job

  (...)
  [queue_job]
  channels = root:4

* Confirm the runner is starting correctly by checking the odoo log file:

.. code-block:: none

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

Usage
=====

To use this module, you need to:

#. Go to ``Job Queue`` menu

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: https://runbot.odoo-community.org/runbot/230/10.0

Known issues / Roadmap
======================

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

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/OCA/queue/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smashing it by providing a detailed and welcomed feedback.

Credits
=======

Images
------

* Odoo Community Association: `Icon <https://github.com/OCA/maintainer-tools/blob/master/template/module/static/description/icon.svg>`_.

Contributors
------------

* Guewen Baconnier <guewen.baconnier@camptocamp.com>
* Stéphane Bidoul <stephane.bidoul@acsone.eu>
* Matthieu Dietrich <matthieu.dietrich@camptocamp.com>
* Jos De Graeve <Jos.DeGraeve@apertoso.be>
* David Lefever <dl@taktik.be>
* Laurent Mignon <laurent.mignon@acsone.eu>
* Laetitia Gangloff <laetitia.gangloff@acsone.eu>

Maintainer
----------

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

This module is maintained by the OCA.

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

To contribute to this module, please visit https://odoo-community.org.
