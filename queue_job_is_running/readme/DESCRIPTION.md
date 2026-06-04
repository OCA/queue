This addon provides the `queue.job.status.mixin` mixin. It displays a warning banner on
a form view when the record has one or more non-terminal queue jobs and lists their
names.

The status is read directly from `queue.job`, so no method is required to mark a job as
running or finished.
