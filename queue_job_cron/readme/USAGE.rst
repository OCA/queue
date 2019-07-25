To use this module, you need to:

#. Go to a scheduled action, a flag "Run as queue job" will allow you to run
the action as a queue job. You will also allowed to select a channel of its
execution.
To configure dedicated channels please refers to queue_job help: https://github.com/OCA/queue/blob/12.0/queue_job/README.rst

Channels can be used to manage sequential jobs and prevent concurrency accesses.
To do that you just have to define a channel per cron limited to 1 at time.
