# Copyright 2025 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    cr.execute(
        """
        UPDATE queue_job_batch
        SET state = 'pending'
        WHERE state = 'draft'
        """
    )
    cr.execute(
        """
        UPDATE queue_job_batch
        SET is_read = FALSE
        WHERE state != 'finished' AND is_read
        """
    )
