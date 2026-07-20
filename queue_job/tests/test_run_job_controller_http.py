# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from unittest import mock

from odoo import SUPERUSER_ID, http
from odoo.tests.common import HttpCase, tagged

from ..controllers.main import RunJobController


@tagged("-at_install", "post_install")
class TestRunJobHttp(HttpCase):
    """End-to-end tests for the ``/queue_job/runjob`` endpoint.

    ``runjob`` is declared ``auth="none"``, so ``_auth_method_none`` pins
    ``transaction.default_env`` to an env with ``uid=None``. The controller
    must additionally repoint ``default_env`` to a superuser env, otherwise
    any flush during ``job.perform()`` that goes through
    ``Transaction.flush() -> default_env.flush_all()`` recomputes stored
    fields with ``self.env.user`` as an empty recordset. See #922.
    """

    def _capture_default_env_uid_at_acquire(self):
        """Hit ``/queue_job/runjob`` and observe ``transaction.default_env.uid``
        at the moment ``_acquire_job`` is entered.

        ``_acquire_job`` is patched to return ``None`` so the endpoint exits
        without performing the job. This avoids the commit inside
        ``_acquire_job``, which is forbidden inside tests, and is sufficient
        to observe the env state established by the request-handling
        machinery: nothing between ``update_env`` and ``_acquire_job``
        touches ``transaction.default_env``, so the value seen here is the
        same value a job would see at ``perform()`` time.

        HttpCase runs the HTTP server in the same process, so class-level
        ``mock.patch`` calls take effect on the server side as well.
        """
        captured = {}

        def spy(cls, env, job_uuid):
            captured["default_env_uid"] = env.transaction.default_env.uid
            return None

        with mock.patch.object(RunJobController, "_acquire_job", classmethod(spy)):
            response = self.url_open(
                f"/queue_job/runjob?db={self.env.cr.dbname}&job_uuid=stub"
            )
            response.raise_for_status()

        return captured.get("default_env_uid")

    def test_runjob_pins_default_env_to_superuser(self):
        """``runjob`` must set ``transaction.default_env`` to a superuser env.

        Verifies that by the time ``_acquire_job`` is entered,
        ``env.transaction.default_env.uid`` is ``SUPERUSER_ID``. This is the
        state that lets flushes triggered by the job recompute stored fields
        with a real ``self.env.user`` rather than an empty recordset.
        """
        default_env_uid = self._capture_default_env_uid_at_acquire()
        self.assertEqual(default_env_uid, SUPERUSER_ID)

    def test_runjob_without_updating_default_env_leaves_uid_none(self):
        """Repointing ``default_env`` is the specific mechanism this relies on.

        Neutralises ``http.request.update_env`` for the duration of the
        request, matching what happens if a ``runjob`` implementation only
        obtains a local superuser env via ``http.request.env(user=...)``
        without invoking ``update_env``. The observable ``default_env.uid``
        then remains at the ``None`` value installed by
        ``_auth_method_none``. This isolates ``default_env`` repointing as
        the load-bearing behavior of ``runjob``: any future refactor that
        drops it will trip this test.
        """

        def no_op_update_env(self_, user=None, context=None, su=None):
            """Alternative ``Request.update_env`` that intentionally does
            nothing. Simulates a controller that never asks the request to
            update its environment.
            """

        with mock.patch.object(http.Request, "update_env", no_op_update_env):
            default_env_uid = self._capture_default_env_uid_at_acquire()

        self.assertIsNone(default_env_uid)
