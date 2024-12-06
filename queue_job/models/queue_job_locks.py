# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class QueueJobLocks(models.AbstractModel):

    _name = "queue.job.locks"
    _description = "Queue Job Locks"

    def init(self):
        # Create job lock table
        self.env.cr.execute(
            """
                CREATE TABLE IF NOT EXISTS queue_job_locks (
                    id INT PRIMARY KEY,
                    CONSTRAINT
                        queue_job_locks_queue_job_id_fkey
                    FOREIGN KEY (id)
                    REFERENCES queue_job (id) ON DELETE CASCADE
                );
            """
        )
