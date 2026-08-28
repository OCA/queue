
## 19.0.2.0.4 (2026-08-28)

- [FIX] Remove reference to base.user_admin (removed in Odoo 17+)
  causing -u queue_job to fail on Odoo 17/18/19.
  The xmlid base.user_admin was removed in Odoo 17; users should be
  added to the group via backoffice instead.
  Backport from verbum_core fork (neoand/verbum#commit pending).

## Next

- \[ADD\] Run jobrunner as a worker process instead of a thread in the
  main process (when running with --workers \> 0)
- \[REF\] `@job` and `@related_action` deprecated, any method can be
  delayed, and configured using `queue.job.function` records
- \[MIGRATION\] from 13.0 branched at rev. e24ff4b
