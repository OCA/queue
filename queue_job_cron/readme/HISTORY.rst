16.0.2.0.0 (2024-01-08)
~~~~~~~~~~~~~~~~~~~~~~~

**Features**

- By default prevent parallel run of the same cron job when run as queue job.

  When a cron job is run by odoo, the odoo runner will prevent parallel run
  of the same cron job. Before this change, this was not the case when the
  cron job was run as a queue job. A new option is added to the cron job when
  run as a queue job to prevent parallel run. This option is set to True by
  default. In this way, the behavior is now the same as when the cron job is run
  by odoo but you keep the possibility to disable this restriction when run as
  a queue job. (`#612 <https://github.com/OCA/queue/issues/612>`_)
