
[![Runboat](https://img.shields.io/badge/runboat-Try%20me-875A7B.png)](https://runboat.odoo-community.org/builds?repo=OCA/queue&target_branch=16.0)
[![Pre-commit Status](https://github.com/OCA/queue/actions/workflows/pre-commit.yml/badge.svg?branch=16.0)](https://github.com/OCA/queue/actions/workflows/pre-commit.yml?query=branch%3A16.0)
[![Build Status](https://github.com/OCA/queue/actions/workflows/test.yml/badge.svg?branch=16.0)](https://github.com/OCA/queue/actions/workflows/test.yml?query=branch%3A16.0)
[![codecov](https://codecov.io/gh/OCA/queue/branch/16.0/graph/badge.svg)](https://codecov.io/gh/OCA/queue)
[![Translation Status](https://translation.odoo-community.org/widgets/queue-16-0/-/svg-badge.svg)](https://translation.odoo-community.org/engage/queue-16-0/?utm_source=widget)

<!-- /!\ do not modify above this line -->

# Odoo Queue Job

Asynchronous Job Queue. Delay Model methods in asynchronous jobs, executed in the background as soon as possible or on a schedule. Support Channels to segregates jobs in different queues with different capacities. Unlike scheduled tasks, a job captures arguments for later processing.

<!-- /!\ do not modify below this line -->

<!-- prettier-ignore-start -->

[//]: # (addons)

Available addons
----------------
addon | version | maintainers | summary
--- | --- | --- | ---
[base_export_async](base_export_async/) | 16.0.1.0.0 |  | Asynchronous export with job queue
[base_import_async](base_import_async/) | 16.0.1.1.2 |  | Import CSV files in the background
[queue_job](queue_job/) | 16.0.2.6.8 | [![guewen](https://github.com/guewen.png?size=30px)](https://github.com/guewen) | Job Queue
[queue_job_batch](queue_job_batch/) | 16.0.1.0.1 |  | Job Queue Batch
[queue_job_cron](queue_job_cron/) | 16.0.2.0.0 |  | Scheduled Actions as Queue Jobs
[queue_job_cron_jobrunner](queue_job_cron_jobrunner/) | 16.0.1.0.0 | [![ivantodorovich](https://github.com/ivantodorovich.png?size=30px)](https://github.com/ivantodorovich) | Run jobs without a dedicated JobRunner
[queue_job_subscribe](queue_job_subscribe/) | 16.0.1.0.0 |  | Control which users are subscribed to queue job notifications
[queue_job_web_notify](queue_job_web_notify/) | 16.0.1.0.0 |  | This module allows to display a notification to the related user of a failed job. It uses the web_notify notification feature.
[test_queue_job](test_queue_job/) | 16.0.2.2.2 |  | Queue Job Tests
[test_queue_job_batch](test_queue_job_batch/) | 16.0.1.0.0 |  | Test Job Queue Batch


Unported addons
---------------
addon | version | maintainers | summary
--- | --- | --- | ---
[test_base_import_async](test_base_import_async/) | 14.0.1.0.1 (unported) |  | Test suite for base_import_async. Normally you don't need to install this.

[//]: # (end addons)

<!-- prettier-ignore-end -->

## Licenses

This repository is licensed under [AGPL-3.0](LICENSE).

However, each module can have a totally different license, as long as they adhere to Odoo Community Association (OCA)
policy. Consult each module's `__manifest__.py` file, which contains a `license` key
that explains its license.

----
OCA, or the [Odoo Community Association](http://odoo-community.org/), is a nonprofit
organization whose mission is to support the collaborative development of Odoo features
and promote its widespread use.
