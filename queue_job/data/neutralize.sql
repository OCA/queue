UPDATE queue_job
SET state = 'cancelled'
WHERE state in ('wait_dependencies', 'pending', 'enqueued', 'started');
