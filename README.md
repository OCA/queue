[![Build Status](https://travis-ci.org/OCA/queue.svg?branch=11.0)](https://travis-ci.org/OCA/queue)
[![codecov](https://codecov.io/gh/OCA/queue/branch/11.0/graph/badge.svg)](https://codecov.io/gh/OCA/queue)


Odoo Queue Modules
==================

Asynchronous Job Queue. Delay Model methods in asynchronous jobs, executed in
the background as soon as possible or on a schedule.  Support Channels to
segregates jobs in different queues with different capacities. Unlike
scheduled tasks, a job captures arguments for later processing.


[//]: # (addons)

Available addons
----------------
addon | version | summary
--- | --- | ---
[base_import_async](base_import_async/) | 11.0.2.0.0 | Import CSV files in the background
[mail_queue_job](mail_queue_job/) | 11.0.1.0.1 | Mail Queue Job
[queue_job](queue_job/) | 11.0.1.1.0 | Job Queue
[queue_job_batch](queue_job_batch/) | 11.0.1.1.1 | Job Queue Batch
[queue_job_subscribe](queue_job_subscribe/) | 11.0.1.0.0 | Control which users are subscribed to queue job notifications
[test_base_import_async](test_base_import_async/) | 11.0.1.0.0 | Test suite for base_import_async. Normally you don't need to install this.
[test_queue_job](test_queue_job/) | 11.0.1.0.0 | Queue Job Tests
[test_queue_job_batch](test_queue_job_batch/) | 11.0.1.1.0 | Test Job Queue Batch

[//]: # (end addons)

Translation Status
------------------
[![Transifex Status](https://www.transifex.com/projects/p/OCA-queue-11-0/chart/image_png)](https://www.transifex.com/projects/p/OCA-queue-11-0)

