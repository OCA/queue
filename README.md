
[![Runboat](https://img.shields.io/badge/runboat-Try%20me-875A7B.png)](https://runboat.odoo-community.org/builds?repo=OCA/queue&target_branch=17.0)
[![Pre-commit Status](https://github.com/OCA/queue/actions/workflows/pre-commit.yml/badge.svg?branch=17.0)](https://github.com/OCA/queue/actions/workflows/pre-commit.yml?query=branch%3A17.0)
[![Build Status](https://github.com/OCA/queue/actions/workflows/test.yml/badge.svg?branch=17.0)](https://github.com/OCA/queue/actions/workflows/test.yml?query=branch%3A17.0)
[![codecov](https://codecov.io/gh/OCA/queue/branch/17.0/graph/badge.svg)](https://codecov.io/gh/OCA/queue)
[![Translation Status](https://translation.odoo-community.org/widgets/queue-17-0/-/svg-badge.svg)](https://translation.odoo-community.org/engage/queue-17-0/?utm_source=widget)

<!-- /!\ do not modify above this line -->

# Queue Job

Asynchronous Job Queue. Delay Model methods in asynchronous jobs, executed in the background as soon as possible or on a schedule. Support Channels to segregates jobs in different queues with different capacities. Unlike scheduled tasks, a job captures arguments for later processing.

<!-- /!\ do not modify below this line -->

<!-- prettier-ignore-start -->

[//]: # (addons)

Available addons
----------------
addon | version | maintainers | summary
--- | --- | --- | ---
[queue_job](queue_job/) | 17.0.1.0.3 | [![guewen](https://github.com/guewen.png?size=30px)](https://github.com/guewen) | Job Queue
[queue_job_cron](queue_job_cron/) | 17.0.1.0.0 |  | Scheduled Actions as Queue Jobs
[queue_job_cron_jobrunner](queue_job_cron_jobrunner/) | 17.0.1.0.0 | [![ivantodorovich](https://github.com/ivantodorovich.png?size=30px)](https://github.com/ivantodorovich) | Run jobs without a dedicated JobRunner
[queue_job_subscribe](queue_job_subscribe/) | 17.0.1.0.0 |  | Control which users are subscribed to queue job notifications
[test_queue_job](test_queue_job/) | 17.0.1.0.1 |  | Queue Job Tests

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
