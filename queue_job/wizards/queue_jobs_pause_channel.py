from odoo import fields, models


class QueueChannelPause(models.TransientModel):
    _name = "queue.channel.pause"
    _description = "Wizard to change jobs to channel paused"

    job_ids = fields.Many2many(
        comodel_name="queue.job", string="Jobs", default=lambda r: r._default_job_ids()
    )

    def _default_job_ids(self):
        res = False
        context = self.env.context
        if context.get("active_model") == "queue.job" and context.get("active_ids"):
            res = context["active_ids"]
        return res

    def set_channel_paused(self):
        self.job_ids._validate_state_jobs()
        self.job_ids.set_channel_pause()
        return {"type": "ir.actions.act_window_close"}
