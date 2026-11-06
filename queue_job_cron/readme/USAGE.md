To use this module, you need to:

#\. Go to a scheduled action, a flag "Run as queue job" will allow you
to run the action as a queue job. You will also allowed to select a
channel of its execution. To configure dedicated channels please refers
to queue_job help:
<https://github.com/OCA/queue/blob/12.0/queue_job/README.rst>

Like odoo does for regular crons, the same cron is never run twice at the
same time, unless "No Parallel Queue Job Run" is unchecked: the job holds
the cron lock while it runs, and a second job of the same cron is postponed
until the first one ends. Channels can still be used to limit how many
different crons run at the same time.
