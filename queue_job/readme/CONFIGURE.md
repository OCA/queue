- Using environment variables and command line:
  - Adjust environment variables (optional):
    - `ODOO_QUEUE_JOB_CHANNELS=root:4` or any other channels
      configuration. The default is `root:1`
    - if `xmlrpc_port` is not set: `ODOO_QUEUE_JOB_PORT=8069`
  - Start Odoo with `--load=web,queue_job` and `--workers` greater than
    1.[^1]
- Using the Odoo configuration file:

``` ini
[options]
(...)
workers = 6
server_wide_modules = web,queue_job

(...)
[queue_job]
channels = root:2
```

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
