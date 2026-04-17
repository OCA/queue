import logging

from odoo import http

from .jobrunner import maybe_start_runner_thread

_logger = logging.getLogger(__name__)


def post_load():
    _logger.info(
        "Apply Request._get_session_and_dbname monkey patch to capture db"
        " from request with multiple databases"
    )
    _get_session_and_dbname_orig = http.Request._get_session_and_dbname
    _serve_db_orig = http.Request._serve_db

    def _get_session_and_dbname(self):
        session, dbname = _get_session_and_dbname_orig(self)
        if (
            not dbname
            and self.httprequest.path == "/queue_job/runjob"
            and self.httprequest.args.get("db")
        ):
            dbname = self.httprequest.args["db"]
        return session, dbname

    def _serve_db(self):
        maybe_start_runner_thread("lazy http worker")
        return _serve_db_orig(self)

    http.Request._get_session_and_dbname = _get_session_and_dbname
    http.Request._serve_db = _serve_db
    maybe_start_runner_thread("current http worker")
