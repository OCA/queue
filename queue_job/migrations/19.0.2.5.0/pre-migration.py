# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
from openupgradelib import openupgrade

# The indexes were created in init() with a free text comment. models.Index compares
# the comment with its own definition and rebuilds the index when they differ, so they
# get the comment the ORM expects and are not rebuilt on the first update.
INDEXES = {
    "queue_job_identity_key_state_partial_index": (
        "INDEX (identity_key) "
        "WHERE state in ('pending','enqueued','wait_dependencies') "
        "AND identity_key IS NOT NULL"
    ),
    "queue_job_channel_date_done_date_created_index": (
        "INDEX (channel, date_done, date_created)"
    ),
}


@openupgrade.migrate()
def migrate(env, version):
    cr = env.cr
    for name, definition in INDEXES.items():
        cr.execute("SELECT to_regclass(%s)", [name])
        if cr.fetchone()[0]:
            cr.execute(f'COMMENT ON INDEX "{name}" IS %s', [definition])
