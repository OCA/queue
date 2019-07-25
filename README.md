[![Build Status](https://travis-ci.org/OCA/queue.svg?branch=12.0)](https://travis-ci.org/OCA/queue)
[![codecov](https://codecov.io/gh/OCA/queue/branch/12.0/graph/badge.svg)](https://codecov.io/gh/OCA/queue)


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
[base_export_async](base_export_async/) | 12.0.1.0.0 | Asynchronous export with job queue
[queue_job](queue_job/) | 12.0.1.0.0 | Job Queue
[queue_job_cron](queue_job_cron/) | 12.0.1.0.1 | Scheduled Actions as Queue Jobs
[test_queue_job](test_queue_job/) | 12.0.1.0.0 | Queue Job Tests


Unported addons
---------------
addon | version | summary
--- | --- | ---
[base_import_async](base_import_async/) | 11.0.1.0.0 (unported) | Import CSV files in the background
[queue_job_subscribe](queue_job_subscribe/) | 11.0.1.0.0 (unported) | Control which users are subscribed to queue job notifications
[test_base_import_async](test_base_import_async/) | 11.0.1.0.0 (unported) | Test suite for base_import_async. Normally you don't need to install this.

[//]: # (end addons)

Translation Status
------------------
[![Transifex Status](https://www.transifex.com/projects/p/OCA-queue-12-0/chart/image_png)](https://www.transifex.com/projects/p/OCA-queue-12-0)

