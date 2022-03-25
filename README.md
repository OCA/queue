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
addon | version | maintainers | summary
--- | --- | --- | ---
[base_export_async](base_export_async/) | 12.0.1.1.0 |  | Asynchronous export with job queue
[base_import_async](base_import_async/) | 12.0.2.0.0 |  | Import CSV files in the background
[export_async_schedule](export_async_schedule/) | 12.0.1.0.0 | [![guewen](https://github.com/guewen.png?size=30px)](https://github.com/guewen) | Generate and send exports by emails on a schedule
[queue_job](queue_job/) | 12.0.3.1.2 | [![guewen](https://github.com/guewen.png?size=30px)](https://github.com/guewen) | Job Queue
[queue_job_batch](queue_job_batch/) | 12.0.1.0.1 |  | Job Queue Batch
[queue_job_cron](queue_job_cron/) | 12.0.1.1.1 |  | Scheduled Actions as Queue Jobs
[queue_job_subscribe](queue_job_subscribe/) | 12.0.1.0.0 |  | Control which users are subscribed to queue job notifications
[test_base_import_async](test_base_import_async/) | 12.0.1.0.0 |  | Test suite for base_import_async. Normally you don't need to install this.
[test_queue_job](test_queue_job/) | 12.0.2.0.0 |  | Queue Job Tests
[test_queue_job_batch](test_queue_job_batch/) | 12.0.1.1.0 |  | Test Job Queue Batch

[//]: # (end addons)

Translation Status
------------------
[![Transifex Status](https://www.transifex.com/projects/p/OCA-queue-12-0/chart/image_png)](https://www.transifex.com/projects/p/OCA-queue-12-0)

