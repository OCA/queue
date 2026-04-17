This addon groups related queue jobs into batches.

It lets users monitor a set of queued jobs as a single batch so the
overall execution state is easier to follow.

Create a batch with `queue.job.batch.get_new_batch(...)`, pass it in the
context as `job_batch`, and enqueue jobs with `with_delay()` as usual.

Example:

``` python
from odoo import models, fields, api


class MyModel(models.Model):
    _name = 'my.model'

    def my_method(self, a, k=None):
        _logger.info('executed with a: %s and k: %s', a, k)


class MyOtherModel(models.Model):
    _name = 'my.other.model'

    def button_do_stuff(self):
        batch = self.env['queue.job.batch'].get_new_batch('Group')
        model = self.env['my.model'].with_context(job_batch=batch)
        for i in range(1, 100):
            model.with_delay().my_method('a', k=i)
```

In the snippet of code above, when we call `button_do_stuff`, 100 jobs
capturing the method and arguments will be postponed. It will be
executed as soon as the Jobrunner has a free bucket, which can be
instantaneous if no other job is running.

Once all jobs in the batch have finished, the batch is marked as done.
