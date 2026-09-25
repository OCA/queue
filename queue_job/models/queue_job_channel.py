# Copyright 2013-2020 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)


from odoo import _, api, exceptions, fields, models

from ..jobrunner import runner
from ..jobrunner.channels import RELOAD_PAYLOAD


class QueueJobChannel(models.Model):
    _name = "queue.job.channel"
    _description = "Job Channels"
    _rec_name = "complete_name"

    # fields that trigger a reload of the jobrunner for this database when changed
    _JOBRUNNER_CONFIG_FIELDS = frozenset(
        (
            "capacity",
            "sequential",
            "throttle",
            "paused",
            "name",
            "parent_id",
            "capacity_default",
            "sequential_default",
        )
    )

    name = fields.Char()
    complete_name = fields.Char(
        compute="_compute_complete_name", store=True, readonly=True, recursive=True
    )
    parent_id = fields.Many2one(
        comodel_name="queue.job.channel", string="Parent Channel", ondelete="restrict"
    )
    job_function_ids = fields.One2many(
        comodel_name="queue.job.function",
        inverse_name="channel_id",
        string="Job Functions",
    )
    removal_interval = fields.Integer(
        default=lambda self: self.env["queue.job"]._removal_interval,
        required=True,
        help="Number of days after which done jobs are deleted.",
    )
    capacity = fields.Integer(
        help="Maximum number of jobs running at the same time in this channel. "
        "0 means no limit, but they are still limited by the capacity of the parent "
        "channel. On the root channel, 0 is limited by the global server-wide "
        "configuration."
    )
    sequential = fields.Boolean(
        help="Jobs are executed one after the other and failed jobs block the channel. "
        "Requires a capacity of 1."
    )
    throttle = fields.Integer(
        help="Minimum delay in seconds between the start of two jobs in this channel."
    )
    paused = fields.Boolean(
        help="A paused channel (an its subchannels) do not execute any jobs until "
        "resumed."
    )
    capacity_default = fields.Integer(
        string="Subchannels Default Capacity",
        help="Default capacity for unconfigured subchannels. "
        "0 means they would have the same capacity as the current channel.",
    )
    sequential_default = fields.Boolean(
        string="Subchannels Default Sequential",
        help="If sequential is enabled for unconfigured subchannels.",
    )
    effective_paused = fields.Boolean(
        compute="_compute_effective_paused",
        recursive=True,
        help="If this channel is actually paused, depending on the parents.",
    )
    effective_capacity = fields.Integer(
        compute="_compute_effective_capacity",
        recursive=True,
        help="Actual capacity of this channel. Its own capacity if set, "
        "or the capacity of the closest parent. The root channel "
        "is limited by the server-wide max_capacity/db_max_capacity configuration.",
    )

    _sql_constraints = [
        ("name_uniq", "unique(complete_name)", "Channel complete name must be unique")
    ]

    @api.constrains(
        "capacity", "sequential", "throttle", "capacity_default", "sequential_default"
    )
    def _check_jobrunner_configuration(self):
        for record in self:
            if record.capacity < 0:
                raise exceptions.ValidationError(
                    self.env._("The capacity of a channel cannot be negative.")
                )
            if record.throttle < 0:
                raise exceptions.ValidationError(
                    self.env._("The throttle of a channel cannot be negative.")
                )
            if record.sequential and record.capacity != 1:
                raise exceptions.ValidationError(
                    self.env._("A sequential channel must have a capacity of 1.")
                )
            if record.capacity_default < 0:
                raise exceptions.ValidationError(
                    self.env._("The default capacity of a channel cannot be negative.")
                )
            if record.sequential_default and record.capacity_default != 1:
                raise exceptions.ValidationError(
                    self.env._(
                        "A channel with a sequential default must have a "
                        "default capacity of 1."
                    )
                )

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for record in self:
            if not record.name:
                complete_name = ""  # new record
            elif record.parent_id:
                complete_name = ".".join([record.parent_id.complete_name, record.name])
            else:
                complete_name = record.name
            record.complete_name = complete_name

    @api.depends("paused", "parent_id.effective_paused")
    def _compute_effective_paused(self):
        for record in self:
            record.effective_paused = record.paused or bool(
                record.parent_id and record.parent_id.effective_paused
            )

    @api.depends("capacity", "parent_id.effective_capacity")
    def _compute_effective_capacity(self):
        for record in self:
            if record.parent_id:
                max_capacity = record.parent_id.effective_capacity
            else:
                max_capacity = record._root_max_capacity()
            if record.capacity:
                record.effective_capacity = min(record.capacity, max_capacity)
            else:
                record.effective_capacity = max_capacity

    def _root_max_capacity(self):
        """Server-wide capacity of the root channel for current database."""
        rules = runner.parse_db_max_capacity(runner._db_max_capacity())
        return runner.db_max_capacity_for(
            self.env.cr.dbname, rules, default=runner._max_capacity()
        )

    @api.constrains("parent_id", "name")
    def parent_required(self):
        for record in self:
            if record.name != "root" and not record.parent_id:
                raise exceptions.ValidationError(_("Parent channel required."))

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        if self.env.context.get("install_mode"):
            # installing a module that creates a channel: rebinds the channel
            # to an existing one (likely we already had the channel created by
            # the @job decorator previously)
            new_vals_list = []
            for vals in vals_list:
                name = vals.get("name")
                parent_id = vals.get("parent_id")
                if name and parent_id:
                    existing = self.search(
                        [("name", "=", name), ("parent_id", "=", parent_id)]
                    )
                    if existing:
                        if not existing.get_metadata()[0].get("noupdate"):
                            existing.write(vals)
                        records |= existing
                        continue
                new_vals_list.append(vals)
            vals_list = new_vals_list
        records |= super().create(vals_list)
        records._notify_channel_config_changed()
        return records

    @api.onchange("capacity")
    def _onchange_capacity(self):
        self.capacity_default = self.capacity

    @api.onchange("sequential")
    def _onchange_sequential(self):
        self.sequential_default = self.sequential

    def write(self, values):
        for channel in self:
            if (
                not self.env.context.get("install_mode")
                and channel.name == "root"
                and ("name" in values or "parent_id" in values)
            ):
                raise exceptions.UserError(_("Cannot change the root channel"))
        res = super().write(values)
        if self._JOBRUNNER_CONFIG_FIELDS.intersection(values):
            self._notify_channel_config_changed()
        return res

    def unlink(self):
        for channel in self:
            if channel.name == "root":
                raise exceptions.UserError(_("Cannot remove the root channel"))
        res = super().unlink()
        self._notify_channel_config_changed()
        return res

    def action_pause(self):
        self.write({"paused": True})

    def action_resume(self):
        self.write({"paused": False})

    def _notify_channel_config_changed(self):
        """Notify the jobrunner to reload its configuration"""
        self.env.cr.execute("SELECT pg_notify('queue_job', %s)", (RELOAD_PAYLOAD,))
