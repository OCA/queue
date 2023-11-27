# Copyright 2023 Akretion (http://www.akretion.com).
# @author Florian Mounier <florian.mounier@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import operator
from functools import reduce

from odoo import models

from odoo.addons.queue_job.delay import Delayable


class DelayableBatchRecordset(object):
    __slots__ = ("delayables", "batch")

    def __init__(
        self,
        recordset,
        priority=None,
        eta=None,
        max_retries=None,
        description=None,
        channel=None,
        identity_key=None,
        batch_size=None,
        batch_count=None,
    ):
        total_records = len(recordset)
        if batch_size:
            batch_count = 1 + total_records // batch_size
        else:
            batch_size = total_records // batch_count
            if total_records % batch_count:
                batch_size += 1

        description = description or "__EMPTY__"
        self.batch = recordset.env["queue.job.batch"].get_new_batch(
            "Batch of %s" % description
        )
        self.delayables = []
        for batch in range(batch_count):
            start = batch * batch_size
            end = min((batch + 1) * batch_size, total_records)
            if end > start:
                self.delayables.append(
                    Delayable(
                        recordset[start:end].with_context(job_batch=self.batch),
                        priority=priority or 12,  # Lower priority than default
                        # to let queue_job_batch check the state
                        eta=eta,
                        max_retries=max_retries,
                        description="%s (batch %d/%d)"
                        % (description, batch + 1, batch_count),
                        channel=channel,
                        identity_key=identity_key,
                    )
                )

    @property
    def recordset(self):
        return reduce(operator.or_, self.delayables, set()).recordset

    def __getattr__(self, name):
        def _delay_delayable(*args, **kwargs):
            for delayable in self.delayables:
                func = getattr(delayable, name)

                # FIXME: Find a better way to set default description
                if "__EMPTY__" in delayable.description:
                    description = (
                        func.__doc__.splitlines()[0].strip()
                        if func.__doc__
                        else "{}.{}".format(delayable.recordset._name, name)
                    )
                    delayable.description = delayable.description.replace(
                        "__EMPTY__", description
                    )
                    if "__EMPTY__" in self.batch.name:
                        self.batch.name = self.batch.name.replace(
                            "__EMPTY__", description
                        )
                func(*args, **kwargs).delay()
            self.batch.enqueue()
            return [delayable._generated_job for delayable in self.delayables]

        return _delay_delayable

    def __str__(self):
        recordset = self.delayables[0].recordset
        return "DelayableBatchRecordset(%s%s)" % (
            recordset._name,
            getattr(recordset, "_ids", ""),
        )

    __repr__ = __str__


class Base(models.AbstractModel):
    _inherit = "base"

    def with_delay(
        self,
        priority=None,
        eta=None,
        max_retries=None,
        description=None,
        channel=None,
        identity_key=None,
        batch_size=None,
        batch_count=None,
    ):
        if batch_size or batch_count:
            return DelayableBatchRecordset(
                self,
                priority=priority,
                eta=eta,
                max_retries=max_retries,
                description=description,
                channel=channel,
                identity_key=identity_key,
                batch_size=batch_size,
                batch_count=batch_count,
            )

        return super().with_delay(
            priority=priority,
            eta=eta,
            max_retries=max_retries,
            description=description,
            channel=channel,
            identity_key=identity_key,
        )
