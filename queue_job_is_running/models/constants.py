# Copyright 2026 Ecosoft Co., Ltd. (https://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tools import SQL

from odoo.addons.queue_job.job import ENQUEUED, PENDING, STARTED, WAIT_DEPENDENCIES

#: queue.job states that are not terminal yet (done / cancelled / failed).
RUNNING_STATES = (WAIT_DEPENDENCIES, PENDING, ENQUEUED, STARTED)

RUNNING_RECORD_IDS_INDEX = "queue_job_running_record_ids_gin_idx"

# JobSerialized values created on 18.0 are JSON strings in a jsonb column, while
# migrated values can be JSON objects. Normalize both storage shapes before
# extracting the record ids.
JOB_RECORD_IDS_SQL = SQL(
    "COALESCE(records -> 'ids', ((records #>> '{}')::jsonb) -> 'ids')"
)
