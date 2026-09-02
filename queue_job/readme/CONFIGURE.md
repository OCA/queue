- Using environment variables and command line:
  - Adjust environment variables (optional):
    - `ODOO_QUEUE_JOB_CHANNELS=root:4` or any other channels
    - `ODOO_QUEUE_JOB_MAX_CAPACITY=4`, max number of concurrent jobs (not used if `ODOO_QUEUE_JOB_CHANNELS` is set)
    - `ODOO_QUEUE_JOB_DB_MAX_CAPACITY=2`, max number of concurrent jobs per DB (not used if `ODOO_QUEUE_JOB_CHANNELS` is set)
    - `ODOO_QUEUE_JOB_PORT=8069`, default `--http-port`
    - `ODOO_QUEUE_JOB_SCHEME=https`, default `http`
    - `ODOO_QUEUE_JOB_HOST=load-balancer`, default `--http-interface`
      or `localhost` if unset
    - `ODOO_QUEUE_JOB_HTTP_AUTH_USER=jobrunner`, default empty
    - `ODOO_QUEUE_JOB_HTTP_AUTH_PASSWORD=s3cr3t`, default empty
    - Start Odoo with `--load=web,queue_job` and `--workers` greater than
      1.[^1]
- Using the Odoo configuration file (set either `channels`, either `max_capacity` and `db_max_capacity`)

``` ini
[options]
(...)
workers = 6
server_wide_modules = web,queue_job

(...)
[queue_job]
channels = root:2
max_capacity = 8
db_max_capacity = 3
scheme = https
host = load-balancer
port = 443
http_auth_user = jobrunner
http_auth_password = s3cr3t
```

`db_max_capacity` may be an integer or a pattern such as `prod_*:20,staging:2,*:5`

- Confirm the runner is starting correctly by checking the odoo log
  file:

```
...INFO...queue_job.jobrunner.runner: starting
...INFO...queue_job.jobrunner.runner: initializing database connections
...INFO...queue_job.jobrunner.runner: queue job runner ready for db <dbname>
...INFO...queue_job.jobrunner.runner: database connections ready
```

- Create jobs (eg using `base_import_async`) and observe they start
  immediately and in parallel.
- Tip: to enable debug logging for the queue job, use
  `--log-handler=odoo.addons.queue_job:DEBUG`

[^1]: It works with the threaded Odoo server too, although this way of
    running Odoo is obviously not for production purposes.

* Jobs that remain in `enqueued` or `started` state (because, for instance,
  their worker has been killed) will be automatically re-queued.
