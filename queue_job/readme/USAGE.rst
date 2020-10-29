To use this module, you need to:

#. Go to ``Job Queue`` menu

Developers
~~~~~~~~~~

**Configure default options for jobs**

In earlier versions, jobs could be configured using the ``@job`` decorator.
This is now obsolete, they can be configured using optional ``queue.job.function``
and ``queue.job.channel`` XML records.

Example of channel:

.. code-block:: XML

    <record id="channel_sale" model="queue.job.channel">
        <field name="name">sale</field>
        <field name="parent_id" ref="queue_job.channel_root" />
    </record>

Example of job function:

.. code-block:: XML

    <record id="job_function_sale_order_action_done" model="queue.job.function">
        <field name="model_id" ref="sale.model_sale_order"</field>
        <field name="method">action_done</field>
        <field name="channel_id" ref="channel_sale" />
        <field name="related_action" eval='{"func_name": "custom_related_action"}' />
        <field name="retry_pattern" eval="{1: 60, 2: 180, 3: 10, 5: 300}" />
    </record>

The general form for the ``name`` is: ``<model.name>.method``.

The channel, related action and retry pattern options are optional, they are
documented below.

When writing modules, if 2+ modules add a job function or channel with the same
name (and parent for channels), they'll be merged in the same record, even if
they have different xmlids. On uninstall, the merged record is deleted when all
the modules using it are uninstalled.


**Job function: channel**

The channel where the job will be delayed. The default channel is ``root``.

**Job function: related action**

The *Related Action* appears as a button on the Job's view.
The button will execute the defined action.

The default one is to open the view of the record related to the job (form view
when there is a single record, list view for several records).
In many cases, the default related action is enough and doesn't need
customization, but it can be customized by providing a dictionary on the job
function:

.. code-block:: python

   {
       "enable": False,
       "func_name": "related_action_partner",
       "kwargs": {"name": "Partner"},
   }

* ``enable``: when ``False``, the button has no effect (default: ``True``)
* ``func_name``: name of the method on ``queue.job`` that returns an action
* ``kwargs``: extra arguments to pass to the related action method

Example of related action code:

.. code-block:: python

    class QueueJob(models.Model):
        _inherit = 'queue.job'

        def related_action_partner(self, name):
            self.ensure_one()
            model = self.model_name
            partner = self.records
            action = {
                'name': name,
                'type': 'ir.actions.act_window',
                'res_model': model,
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': partner.id,
            }
            return action


**Job function: retry pattern**

When a job fails with a retryable error type, it is automatically
retried later. By default, the retry is always 10 minutes later.

A retry pattern can be configured on the job function. What a pattern represents
is "from X tries, postpone to Y seconds". It is expressed as a dictionary where
keys are tries and values are seconds to postpone as integers:


.. code-block:: python

   {
       1: 10,
       5: 20,
       10: 30,
       15: 300,
   }

Based on this configuration, we can tell that:

* 5 first retries are postponed 10 seconds later
* retries 5 to 10 postponed 20 seconds later
* retries 10 to 15 postponed 30 seconds later
* all subsequent retries postponed 5 minutes later

**Bypass jobs on running Odoo**

When you are developing (ie: connector modules) you might want
to bypass the queue job and run your code immediately.

To do so you can set `TEST_QUEUE_JOB_NO_DELAY=1` in your enviroment.

**Bypass jobs in tests**

When writing tests on job-related methods is always tricky to deal with
delayed recordsets. To make your testing life easier
you can set `test_queue_job_no_delay=True` in the context.

Tip: you can do this at test case level like this

.. code-block:: python

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(
            cls.env.context,
            test_queue_job_no_delay=True,  # no jobs thanks
        ))

Then all your tests execute the job methods synchronously
without delaying any jobs.
