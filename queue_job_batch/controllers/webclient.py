# Copyright 2025 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.http import request

from odoo.addons.mail.controllers.webclient import WebclientController


class WebClient(WebclientController):
    @classmethod
    def _process_request_for_internal_user(cls, store, name, params):
        result = super()._process_request_for_internal_user(store, name, params)
        if name == "systray_get_queue_job_batches":
            # sudo: bus.bus: reading non-sensitive last id
            bus_last_id = request.env["bus.bus"].sudo()._bus_last_id()
            batches = request.env.user._get_queue_job_batches()
            store.add(batches)
            store.add_global_values(
                queueJobBatchCounter=len(batches),
                queueJobBatchCounterBusId=bus_last_id,
            )
        return result
