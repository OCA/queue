from odoo import _, api, fields, models


class QueueMixin(models.AbstractModel):
    """Include this model within models inherited by an object
    to benefit from default behaviors set here.

    .. code-block:: python

        class TestModel(models.Model):
        _name = 'test'
        _inherit = 'queue_job.mixin'

    It also works fine with existing Odoo models::

    .. code-block:: python

        class AccMove(models.Model):
            _inherit = [
                'account.move',
                'queue_job.mixin',
            ]
            _name = 'account.move'

    In the derived class view, add the following lines::

    .. code-block:: xml

        <button name="open_queue_jobs"
            type="object"
            class="oe_stat_button"
            icon="fa-list">
            <field name="queue_job_count" string="QJobs" widget="statinfo" />
        </button>
    """

    _name = "queue.mixin"
    _description = "Queue Mixin"

    @api.depends("queue_job_ids")
    def _compute_queue_job_count(self):
        for record in self:
            record.queue_job_count = (
                len(record.queue_job_ids)
            )

    queue_job_count = fields.Integer(
        compute=_compute_queue_job_count,
        string="Queue job count",
        store=True,
    )

    queue_job_ids = fields.Many2many(
        comodel_name="queue.job",
        column1="record_id",
        column2="job_id",
        string="Queue jobs",
        copy=False,
        readonly=True,
    )

    def open_queue_jobs(self):
        """Display queue jobs related to this model.
        """

        self.ensure_one()

        return {
            "context": self._context,
            "domain": [("id", "in", self.queue_job_ids.ids)],
            "name": _("%s - Queue jobs") % self.name,
            "res_model": "queue.job",
            "type": "ir.actions.act_window",
            "view_mode": "tree,form",
        }
