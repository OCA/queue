[![Build Status](https://travis-ci.org/OCA/queue.svg?branch=8.0)](https://travis-ci.org/OCA/queue)
[![codecov](https://codecov.io/gh/OCA/queue/branch/8.0/graph/badge.svg)](https://codecov.io/gh/OCA/queue)


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
[queue_job](queue_job/) | 8.0.1.0.0 | Job Queue
[queue_job_subscribe](queue_job_subscribe/) | 8.0.1.0.0 | Control which users are subscribed to queue job notifications
[test_queue_job](test_queue_job/) | 8.0.1.0.0 | Queue Job Tests

[//]: # (end addons)

Translation Status
------------------
[![Transifex Status](https://www.transifex.com/projects/p/OCA-queue-8-0/chart/image_png)](https://www.transifex.com/projects/p/OCA-queue-8-0)

