# Copyright (c) 2015-2016 ACSONE SA/NV (<http://acsone.eu>)
# Copyright 2015-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import _

from ....queue_job.jobrunner.channels import Channel, ChannelManager, split_strip
from ..job import PAUSE_CHANNEL


class ChannelPause(Channel):
    def __str__(self):
        default_capacity = "0" if self.name == PAUSE_CHANNEL else "∞"
        capacity = default_capacity if not self.capacity else str(self.capacity)
        return "%s(C:%s,Q:%d,R:%d,F:%d)" % (
            self.fullname,
            capacity,
            len(self._queue),
            len(self._running),
            len(self._failed),
        )

    def has_capacity(self):
        """This method has been copied entirely from the parent class."""
        if self.sequential and self._failed:
            # a sequential queue blocks on failed jobs
            return False
        # MODIFY: the original logic was: `if not self.capacity:`
        if not self.capacity and self.fullname != PAUSE_CHANNEL:
            # unlimited capacity
            return True
        return len(self._running) < self.capacity


class ChannelManagerPause(ChannelManager):
    @classmethod
    def parse_simple_config(cls, config_string):
        """This method has been copied entirely from the parent class."""
        res = []
        config_string = config_string.replace("\n", ",")
        for channel_config_string in split_strip(config_string, ","):
            if not channel_config_string:
                # ignore empty entries (commented lines, trailing commas)
                continue
            config = {}
            config_items = split_strip(channel_config_string, ":")
            name = config_items[0]
            if not name:
                raise ValueError(
                    _("Invalid channel config %s: missing channel name", config_string)
                )
            config["name"] = name
            if len(config_items) > 1:
                capacity = config_items[1]
                try:
                    config["capacity"] = int(capacity)
                    # MODIFY: Add the `if` logic.
                    if name == PAUSE_CHANNEL and config["capacity"] != 0:
                        raise Exception(
                            _("Channel 'pause' must be capacity equal to zero")
                        )
                except Exception as ex:
                    raise ValueError(
                        _(
                            f"Invalid channel config {config_string}: "
                            f"invalid capacity {capacity}"
                        )
                    ) from ex
                for config_item in config_items[2:]:
                    kv = split_strip(config_item, "=")
                    if len(kv) == 1:
                        k, v = kv[0], True
                    elif len(kv) == 2:
                        k, v = kv
                    else:
                        raise ValueError(
                            _(
                                f"Invalid channel config {config_string}: "
                                f"incorrect config item {config_item}",
                            )
                        )
                    if k in config:
                        raise ValueError(
                            _(
                                f"Invalid channel config {config_string}: "
                                f"duplicate key {k}",
                            )
                        )
                    config[k] = v
            else:
                # MODIFY: the original logic was `config["capacity"] = 1`
                config["capacity"] = 0 if name == PAUSE_CHANNEL else 1
            res.append(config)
        return res
