This addon adds profiling controls to queue job functions and wraps
queue job execution in an Odoo profiler session when enabled.

When profiling is enabled for a job function and the executing user
matches the configured profiling user, the queue job runner records
SQL and async stack traces via `odoo.tools.profiler.Profiler` and saves
the results into `ir_profile`.