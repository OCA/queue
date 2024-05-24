from odoo import api, models


class Base(models.AbstractModel):
    _inherit = "base"

    @api.model
    def _job_prepare_context_before_enqueue_keys(self):
        """Keys to keep in context of stored jobs
        Empty by default for backward compatibility.
        """
        res = super()._job_prepare_context_before_enqueue_keys()
        res += ("default_move_type",)
        return res
