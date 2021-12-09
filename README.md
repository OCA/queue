[![Runbot Status](https://runbot.odoo-community.org/runbot/badge/flat/230/15.0.svg)](https://runbot.odoo-community.org/runbot/repo/github-com-oca-queue-230)
[![Build Status](https://travis-ci.com/OCA/queue.svg?branch=15.0)](https://travis-ci.com/OCA/queue)
[![codecov](https://codecov.io/gh/OCA/queue/branch/15.0/graph/badge.svg)](https://codecov.io/gh/OCA/queue)
[![Translation Status](https://translation.odoo-community.org/widgets/queue-15-0/-/svg-badge.svg)](https://translation.odoo-community.org/engage/queue-15-0/?utm_source=widget)

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
[queue_job](queue_job/) | 15.0.1.0.0 | [![guewen](https://github.com/guewen.png?size=30px)](https://github.com/guewen) | Job Queue
[test_queue_job](test_queue_job/) | 15.0.1.0.0 |  | Queue Job Tests


Unported addons
---------------
addon | version | maintainers | summary
--- | --- | --- | ---
[base_export_async](base_export_async/) | 12.0.1.0.0 (unported) |  | Asynchronous export with job queue
[base_import_async](base_import_async/) | 14.0.1.0.1 (unported) |  | Import CSV files in the background
[queue_job_cron](queue_job_cron/) | 14.0.1.0.0 (unported) |  | Scheduled Actions as Queue Jobs
[queue_job_subscribe](queue_job_subscribe/) | 14.0.1.0.0 (unported) |  | Control which users are subscribed to queue job notifications
[test_base_import_async](test_base_import_async/) | 14.0.1.0.1 (unported) |  | Test suite for base_import_async. Normally you don't need to install this.

[//]: # (end addons)

<!-- prettier-ignore-end -->

## Licenses

This repository is licensed under [AGPL-3.0](LICENSE).

However, each module can have a totally different license, as long as they adhere to OCA
policy. Consult each module's `__manifest__.py` file, which contains a `license` key
that explains its license.

----

OCA, or the [Odoo Community Association](http://odoo-community.org/), is a nonprofit
organization whose mission is to support the collaborative development of Odoo features
and promote its widespread use.
