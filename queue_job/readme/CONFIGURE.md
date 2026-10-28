There are two ways to configure the job runner:

Set `channels` (or `ODOO_QUEUE_JOB_CHANNELS`) and every database shares the
same channel tree (we will call it server-wide channels):

``` ini
[queue_job]
channels = root:10,root.priority:3,root.slow:1
```

Leave `channels` unset and set `max_capacity` instead. The job runner then
builds a separate channel tree for each database, based on the *Job Channels*
configured on each database (we will call it per-database channels).

``` ini
[queue_job]
max_capacity = 10
```

`channels` always has precedence over `max_capacity`. If `channels` is set, the
per-database configuration is not used. If neither `channels` nor
`max_capacity` are set, the default execution mode is per-database channels
with a `max_capacity` of 1.

In the per-database mode, channels are configured from the *Job Channels* menu
(or by XML data, see the Usage) instead of a global configuration string.

Alongside `max_capacity`, a global configuration `db_max_capacity` can be set.
It represents the max number of jobs executed at the same time for a single
database (capped by the `max_capacity` anyway):

``` ini
[queue_job]
max_capacity = 10
db_max_capacity = 3  # no more than 3 simultaneous jobs per database
```

`db_max_capacity` may be an integer or a pattern such as
`prod_*:20,staging:2,*:5`, where the first match wins. When using a pattern,
unmatched databases can be configured by a global pattern at the end (`*:n`),
otherwise they will use the `max_capacity`.

The root channel capacity of a database can still be set independently,
however, will in any case be capped by the global `max_capacity` and
`db_max_capacity` parameters.

When set to 0, `max_capacity` or `db_max_capacity` means there is no jobs executed.

Editing a channel's capacity, sequential flag, throttle or set it to pause from
the *Job Channels* menu **is applied live on the job runner**.

> [!NOTE]
> A new database still needs the jobrunner to be restarted.

When using the server-wide channels, the configuration is static and loaded at
startup of the jobrunner.

The execution of channels by the job runner is defined by:

- `capacity`: max number of jobs running at once in the channel (`0` means no
  limit of its own, the parent channel and `max_capacity` or `db_max_capacity`
  still apply)
- `sequential`: jobs run one after the other, and a failed job blocks the
  channel (requires a capacity of 1)
- `throttle`: minimum delay, in seconds, between the start of two jobs
- `paused`: stop running jobs in this channel and its subchannels


**Job Runner Configuration Parameters**

- Using environment variables:
  - Adjust environment variables (optional):
    - `ODOO_QUEUE_JOB_CHANNELS=root:4` or any other channels for server-wide
      channels
    - `ODOO_QUEUE_JOB_MAX_CAPACITY=4`, max number of concurrent jobs (not used
      if `ODOO_QUEUE_JOB_CHANNELS` is set) for per-database channels
    - `ODOO_QUEUE_JOB_DB_MAX_CAPACITY=2`, max number of concurrent jobs per DB
      (not used if `ODOO_QUEUE_JOB_CHANNELS` is set)
    - `ODOO_QUEUE_JOB_PORT=8069`, default `--http-port`
    - `ODOO_QUEUE_JOB_SCHEME=https`, default `http`
    - `ODOO_QUEUE_JOB_HOST=load-balancer`, default `--http-interface`
      or `localhost` if unset
    - `ODOO_QUEUE_JOB_HTTP_AUTH_USER=jobrunner`, default empty
    - `ODOO_QUEUE_JOB_HTTP_AUTH_PASSWORD=s3cr3t`, default empty
- Using the Odoo configuration file (set either `channels`, either
  `max_capacity` and/or `db_max_capacity`)

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

- Odoo has to be started with `queue_job` as server-wide module, either using
  the command line option `--load=web,queue_job`, either by setting it in the
  Odoo configuration file, and `--workers` greater than 1.[^1]

``` ini
[options]
(...)
workers = 6
server_wide_modules = web,queue_job
```

- Confirm the runner is starting correctly by checking the odoo log
  file:

```
...INFO...queue_job.jobrunner.runner: starting
...INFO...queue_job.jobrunner.runner: initializing database connections
...INFO...queue_job.jobrunner.runner: queue job runner ready for db <dbname>
...INFO...queue_job.jobrunner.runner: database connections ready
```

- Create jobs (you can create test jobs by opening
  `https://yourodoourl/queue_job/create_test_job`) and observe they start
  immediately and in parallel.
- Tip: to enable debug logging for the queue job, use
  `--log-handler=odoo.addons.queue_job:DEBUG`

[^1]: It works with the threaded Odoo server too, although this way of
    running Odoo is obviously not for production purposes.


**Migrating from server-wide channels to per-database channels**

As long as `channels` (or `ODOO_QUEUE_JOB_CHANNELS`) is set, the job
runner keeps using the server-wide channels.

To move to channels per database:

1. Configure the channels you need on each database, from the *Job
   Channels* menu: capacity, sequential, throttle, pause
2. Once this configuration is done, remove the `channels` options and set
   `max_capacity` (and optionally `db_max_capacity`) instead (or their
   corresponding environment variables)
3. Restart the job runner
