/** @odoo-module **/

import {QueueJobBatchMenuContainer} from "./batch_menu_container_view.esm";

import {registry} from "@web/core/registry";

const systrayRegistry = registry.category("systray");

export const systrayService = {
    start() {
        systrayRegistry.add(
            "queue_job_batch.QueueJobBatchMenu",
            {Component: QueueJobBatchMenuContainer},
            {sequence: 99}
        );
    },
};

const serviceRegistry = registry.category("services");
serviceRegistry.add("queuebatch_systray_service", systrayService);
