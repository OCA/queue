# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
# ruff: noqa: F821
# pylint: disable=W8116
"""Benchmark queue_job execution throughput

Before running the benchmark, install a fresh database with the `queue_job`
module. If you want to test throughput on several databases, copy the number of
required databases. E.g.

```bash
odoo -c odoorc -d benchmark_template \
--load=web,queue_job --workers=0 --log-level=warn -i queue_job --stop-after-init

createdb -T benchmark_template bench0
createdb -T benchmark_template bench1
createdb -T benchmark_template bench2
```

Then configure whatever you want to test before running the benchmark:

* workers
* db_maxconn
* queue_job channels (server-side) or max_capacity / db_max_capacity: ensure you left
  them blank in the configuration file if you want to pass them as environment variables
  for the test, otherwise you can set them directly in the configuration file

Note: max_cron_threads is forced to 0 to prevent neighbour noise.

Run the benchmark with, e.g.:

```bash
ODOO_QUEUE_JOB_CHANNELS=root:8 \
BENCHMARK_DATABASES=bench0,bench1,bench2 \
BENCHMARK_JOBS=5000 \
odoo shell -c odoorc --log-level=warn < queue_job/scripts/benchmark_jobs.py
```

Or

```bash
ODOO_QUEUE_JOB_MAX_CAPACITY=8 \
BENCHMARK_DATABASES=bench0,bench1,bench2 \
BENCHMARK_JOBS=5000 \
odoo shell -c odoorc --log-level=warn < queue_job/scripts/benchmark_jobs.py
```

Environment variables:

* BENCHMARK_DATABASES: comma separated list of databases to benchmark
* BENCHMARK_JOBS: number of jobs to enqueue in each database (default: 1000)
* BENCHMARK_DURATION: duration (sleep) of each job in seconds (default: 0)
* BENCHMARK_CHANNEL: channel to enqueue into (default: root)
* BENCHMARK_TIMEOUT: maximum seconds to wait for completion (default 600)
* BENCHMARK_ODOORC: odoo config file passed to the jobrunner subprocess
  (default: odoorc)
* BENCHMARK_ODOO_BIN: odoo executable used to start the jobrunner
  subprocess (default: odoo)

Jobrunner-specific environment variables (e.g. ODOO_QUEUE_JOB_CHANNELS) are
inherited from the current environment.

Statistics:

* throughput
* queue time, from the moment the jobrunner is started to the moment jobs are started,
  there is a bit of delay for odoo workers startup though
* the execution time (average and p95): should be equal to the duration of the job
  duration (`BENCHMARK_DURATION` if set) with a slight overhead
* max number of connections on the database(s)

"""

import os
import subprocess
import time
from datetime import datetime

JOBS = int(os.environ.get("BENCHMARK_JOBS", "1000"))
DURATION = float(os.environ.get("BENCHMARK_DURATION", "0"))
CHANNEL = os.environ.get("BENCHMARK_CHANNEL", "root")
TIMEOUT = int(os.environ.get("BENCHMARK_TIMEOUT", "600"))
ODOORC = os.environ.get("BENCHMARK_ODOORC", "odoorc")
ODOO_BIN = os.environ.get("BENCHMARK_ODOO_BIN", "odoo")
DATABASES = [
    db.strip()
    for db in os.environ.get("BENCHMARK_DATABASES", "").split(",")
    if db.strip()
]
if not DATABASES:
    raise SystemExit("BENCHMARK_DATABASES is required")
MULTI_DB = len(DATABASES) > 1


def poll(run, databases, timeout, multi_db, jobrunner_started_at):
    print(f"polling run {run!r} on {databases}...")

    deadline = time.time() + timeout
    max_connections = {dbname: 0 for dbname in databases}
    results = {}
    while True:
        all_done = False
        for dbname in databases:
            with odoo.modules.registry.Registry(dbname).cursor() as cr:
                cr.execute(
                    """
                    SELECT
                        count(*),
                        count(*) FILTER (WHERE state = 'done'),
                        count(*) FILTER (WHERE state = 'failed'),
                        min(date_started),
                        max(date_done),
                        avg(exec_time),
                        percentile_cont(0.95) WITHIN GROUP (ORDER BY exec_time),
                        avg(extract(epoch FROM date_started - %(runner_start)s)),
                        percentile_cont(0.95) WITHIN GROUP (
                            ORDER BY extract(
                                epoch FROM date_started - %(runner_start)s
                            )
                        ),
                        max(extract(epoch FROM date_started - %(runner_start)s))
                    FROM queue_job WHERE name = %(run)s
                    """,
                    {"run": run, "runner_start": jobrunner_started_at},
                )
                (
                    total,
                    done,
                    failed,
                    started_at,
                    done_at,
                    avg_exec,
                    p95_exec,
                    avg_queue,
                    p95_queue,
                    max_queue,
                ) = cr.fetchone()

                cr.execute(
                    "SELECT count(*) FROM pg_stat_activity"
                    " WHERE datname = current_database()"
                )
                (connections,) = cr.fetchone()

            results[dbname] = (
                total,
                done,
                failed,
                started_at,
                done_at,
                avg_exec,
                p95_exec,
                avg_queue,
                p95_queue,
                max_queue,
            )
            max_connections[dbname] = max(max_connections[dbname], connections)

            if failed + done >= total:
                all_done = True

        if all_done:
            break

        if time.time() > deadline:
            print("TIMEOUT:")
            for dbname in databases:
                total, done, failed, *_stats = results[dbname]
                print(f"  [{dbname}] {done} done, {failed} failed of {total}")
            break
        time.sleep(2)

    total_done = total_failed = total_jobs = 0
    summary_started_at = summary_done_at = None
    print()
    for dbname in databases:
        (
            total,
            done,
            failed,
            started_at,
            done_at,
            avg_exec,
            p95_exec,
            avg_queue,
            p95_queue,
            max_queue,
        ) = results[dbname]
        total_done += done
        total_failed += failed
        total_jobs += total

        if started_at and (
            summary_started_at is None or started_at < summary_started_at
        ):
            summary_started_at = started_at
        if done_at and (summary_done_at is None or done_at > summary_done_at):
            summary_done_at = done_at

        prefix = f"[{dbname}] " if multi_db else ""
        elapsed = (done_at - started_at).total_seconds()
        rate = done / elapsed * 60 if elapsed else float("inf")

        print(f"{prefix}jobs:             {total} ({done} done, {failed} failed)")
        print(f"{prefix}wall time:        {elapsed:.1f}s")
        print(f"{prefix}throughput:       {rate:.0f} jobs/minute")
        print(f"{prefix}avg queue time:   {avg_queue:.4f}s")
        print(f"{prefix}p95 queue time:   {p95_queue:.4f}s")
        print(f"{prefix}max queue time:   {max_queue:.4f}s")
        print(f"{prefix}avg exec time:    {avg_exec:.4f}s")
        print(f"{prefix}p95 exec time:    {p95_exec:.4f}s")
        print(f"{prefix}max connections:  {max_connections[dbname]}")

    if multi_db:
        print()
        print("Databases Aggregation")
        if summary_started_at and summary_done_at:
            elapsed = (summary_done_at - summary_started_at).total_seconds()
            rate = total_done / elapsed * 60 if elapsed else float("inf")
            summary = f"{total_done} done, {total_failed} failed"
            print(f"jobs:             {total_jobs} ({summary})")
            print(f"wall time:        {elapsed:.1f}s")
            print(f"throughput:       {rate:.0f} jobs/minute")
        print(f"max connections (peak per db): {max_connections}")


def check_databases_clean(databases):
    db_with_jobs = {}
    for dbname in databases:
        with odoo.modules.registry.Registry(dbname).cursor() as cr:
            cr.execute("SELECT count(*) FROM queue_job")
            (count,) = cr.fetchone()
        if count:
            db_with_jobs[dbname] = count
    if db_with_jobs:
        raise SystemExit(
            f"Cannot start the benchmark, jobs already exist in {db_with_jobs}, "
            "use fresh database(s)."
        )


def start_jobrunner(databases):
    cmd = [
        ODOO_BIN,
        "-c",
        ODOORC,
        "-d",
        ",".join(databases),
        "--load=web,queue_job",
        "--log-level=warn",
        "--max-cron-threads=0",
    ]
    print(f"starting jobrunner with command: {' '.join(cmd)}")
    return subprocess.Popen(cmd)


def stop_jobrunner(process):
    print("stopping jobrunner...")
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def print_config(databases):
    print()
    print("----configuration----")
    print(f"jobs per database: {JOBS} (duration {DURATION}s, channel {CHANNEL!r})")
    print(
        f" workers={odoo.tools.config['workers']}"
        f" db_maxconn={odoo.tools.config['db_maxconn']}"
        " max_cron_threads=0"
    )
    print()


check_databases_clean(DATABASES)

RUN = f"{time.strftime('%Y-%m-%d-%H:%M:%S')}"
print(f"enqueueing {JOBS} jobs in each of {DATABASES} (run {RUN!r})...")

envs = {}
try:
    for dbname in DATABASES:
        cr = odoo.modules.registry.Registry(dbname).cursor()
        envs[dbname] = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

    for i in range(JOBS):
        for dbname in DATABASES:
            envs[dbname]["queue.job"].with_delay(
                channel=CHANNEL, description=RUN
            )._test_job(job_duration=DURATION)
        if (i + 1) % 500 == 0:
            for job_env in envs.values():
                job_env.cr.commit()
            print(f"  {i + 1} jobs enqueued in each of {DATABASES}")
    for job_env in envs.values():
        job_env.cr.commit()
finally:
    for job_env in envs.values():
        job_env.cr.close()

print("jobs enqueued")

jobrunner_started_at = datetime.now()
process = start_jobrunner(DATABASES)
try:
    print_config(DATABASES)
    poll(RUN, DATABASES, TIMEOUT, MULTI_DB, jobrunner_started_at)
finally:
    stop_jobrunner(process)
