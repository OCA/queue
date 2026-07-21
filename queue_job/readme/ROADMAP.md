- After creating a new database or installing `queue_job` on an existing
  database, Odoo must be restarted for the runner to detect it.
- Reload runner configuration on SIGHUP
- `eval_capacity` `workers` should evaluate to sum of all workers across all containers