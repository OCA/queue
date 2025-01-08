import {MailCoreWeb} from "@mail/core/web/mail_core_web_service";
import {patch} from "@web/core/utils/patch";

patch(MailCoreWeb.prototype, {
    setup() {
        super.setup();
        this.busService.subscribe(
            "queue.job.batch/updated",
            (payload, {id: notifId}) => {
                if (
                    payload.batch_created &&
                    notifId > this.store.queueJobBatchCounterBusId
                ) {
                    this.store.queueJobBatchCounter++;
                }
                if (
                    payload.batch_read &&
                    notifId > this.store.queueJobBatchCounterBusId
                ) {
                    this.store.queueJobBatchCounter--;
                }
            }
        );
    },
});
