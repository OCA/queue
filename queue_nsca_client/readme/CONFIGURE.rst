* Access with developer mode
* Access *Settings / NSCA Client / Checks*
* Create all the checks you need for your queue system

The check must have the model *queue.job*, the method *cron_queue_status* and
the following arguments:

- domain: Domain to check (required)
- created_seconds: will only count the jobs older thant this seconds
- critical: Number of records that will mark the critical
- warning: Number of records that will mark the warning

For example, the arguments *[('state', '=', 'failed')], created_seconds=5, critical=2, warning=1*
will return ok if no jobs older than 5 seconds are failed, warning if only one
and otherwise it will return a critical.

The performance data will be the number of jobs found by the domain.
