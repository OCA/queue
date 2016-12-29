# -*- coding: utf-8 -*-

from contextlib import contextmanager
from odoo.addons.queue_job.job import related_action


def start_related_actionify(method, **kwargs):
    related_action(**kwargs)(method)


def stop_related_actionify(method):
    attrs = ('related_action',)
    for attr in attrs:
        if hasattr(method.__func__, attr):
            delattr(method.__func__, attr)


@contextmanager
def related_actionify(method, **kwargs):
    try:
        start_related_actionify(method, **kwargs)
        yield
    finally:
        stop_related_actionify(method)
