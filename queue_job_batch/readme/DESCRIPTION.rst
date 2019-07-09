This addon adds an a grouper for queue jobs.

It allows to show your jobs in a batched form in order to know better the
results.

Example:

.. code-block:: python

  from odoo import models, fields, api
  from odoo.addons.queue_job.job import job

  class MyModel(models.Model):
     _name = 'my.model'

     @api.multi
     @job
     def my_method(self, a, k=None):
         _logger.info('executed with a: %s and k: %s', a, k)


  class MyOtherModel(models.Model):
      _name = 'my.other.model'

      @api.multi
      def button_do_stuff(self):
          batch = self.env['queue.job.batch'].get_new_batch('Group')
          for i in range(1, 100):
              self.env['my.model'].with_context(
                  job_batch=batch
              ).with_delay().my_method('a', k=i)
          batch.enqueue()


In the snippet of code above, when we call ``button_do_stuff``, 100 jobs
capturing the method and arguments will be postponed.  It will be executed as
soon as the Jobrunner has a free bucket, which can be instantaneous if no other
job is running.

Once all the jobs have finished, the grouper will be marked as finished.
