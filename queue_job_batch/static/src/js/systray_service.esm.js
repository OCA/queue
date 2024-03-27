/** @odoo-module **/

import {QueueJobBatchMenuContainer} from "./batch_menu_container_view.esm";
import {registry} from "@web/core/registry";
import session from "web.session";

const systrayRegistry = registry.category("systray");

export const systrayService = {
    start() {
        session
            .user_has_group("queue_job_batch.group_queue_job_batch_user")
            .then(function (has_group) {
                if (has_group) {
                    systrayRegistry.add(
                        "queue_job_batch.QueueJobBatchMenu",
                        {Component: QueueJobBatchMenuContainer},
                        {sequence: 99}
                    );
                }
            });
    },
};

const serviceRegistry = registry.category("services");
serviceRegistry.add("queuebatch_systray_service", systrayService);
