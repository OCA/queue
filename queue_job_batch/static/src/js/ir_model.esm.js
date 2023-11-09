/** @odoo-module **/

import {attr, one} from "@mail/model/model_field";
import {registerModel} from "@mail/model/model_core";

registerModel({
    name: "ir.model.queuejobbatch",
    fields: {
        /**
         * Determines the name of the views that are available for this model.
         */
        availableWebViews: attr({
            compute() {
                return ["kanban", "list", "form", "activity"];
            },
        }),
        queueJobBatch: one("QueueJobBatch", {
            inverse: "irModel",
        }),
        id: attr({
            identifying: true,
        }),
        name: attr(),
        job_count: attr(),
        completeness: attr(),
        failed_percentage: attr(),
        finished_job_count: attr(),
        failed_job_count: attr(),
        state: attr(),
    },
});
