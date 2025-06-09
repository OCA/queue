/* @odoo-module */

import {Store} from "@mail/core/common/store_service";
import {patch} from "@web/core/utils/patch";

// PyToJsModels["queue.job.batch"] = "QueueJobBatch";

patch(Store.prototype, {
    hasQueueJobBatchUserGroup: false,
    queueJobBatchCounterBusId: 0,
    queueJobBatchCounter: 0,

    /** @override */
    get initMessagingParams() {
        return {
            ...super.initMessagingParams,
            systray_get_queue_job_batches: true,
        };
    },
});
