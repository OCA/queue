/*
    Copyright 2025 Camptocamp SA (https://www.camptocamp.com).
    License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
*/
import {Store, pyToJsModels} from "@mail/core/common/store_service";
import {patch} from "@web/core/utils/patch";

pyToJsModels["queue.job.batch"] = "QueueJobBatch";

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
