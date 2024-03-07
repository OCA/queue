This module allows to seemlessly split a big job into smaller jobs.

It uses ``queue_job_batch`` to group the created jobs into a batch.

Example:

.. code-block:: python

  class ResPartner(models.Model):
      # ...

      def copy_all_partners(self):
          # Duplicate all partners in batches of 30:
          self.with_delay(batch_size=30).copy()

  # ...
  self.env['res.partner'].search([], limit=1000).copy_all_partners()

This will create 34 jobs, each one copying 30 partners (except the last one which will copy 10) and will group them into a batch.

Instead of ``batch_size``, one can also use ``batch_count`` to specify the number of batches to create instead.
