/** @odoo-module **/

// ensure components are registered beforehand.
import "./batch_menu_view.esm";
import {getMessagingComponent} from "@mail/utils/messaging_component";

const {Component} = owl;

export class QueueJobBatchMenuContainer extends Component {
    /**
     * @override
     */
    setup() {
        super.setup();
        this.env.services.messaging.modelManager.messagingCreatedPromise.then(() => {
            this.queueJobBatchMenuView =
                this.env.services.messaging.modelManager.messaging.models.QueueJobBatchMenuView.insert();
            this.render();
        });
    }
}

Object.assign(QueueJobBatchMenuContainer, {
    components: {QueueJobBatchMenuView: getMessagingComponent("QueueJobBatchMenuView")},
    template: "queue_job_batch.QueueJobBatchMenuContainer",
});
