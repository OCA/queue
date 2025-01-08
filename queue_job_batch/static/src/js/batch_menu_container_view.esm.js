/** @odoo-module **/

// ensure components are registered beforehand.
import "./batch_menu_view.esm";
import {Component, onWillStart, useState} from "@odoo/owl";
import {MessagingMenu} from "@mail/core/public_web/messaging_menu";
import {useService} from "@web/core/utils/hooks";
import {patch} from "@web/core/utils/patch";

export class QueueJobBatchMenuContainer extends Component {
    /**
     * @override
     */
    setup() {
        // Access the store service using the useService hook
        this.store = useState(useService("mail.store"));

        // Initialize the QueueJobBatchMenuView once store is ready
        onWillStart(async () => {
            this.queueJobBatchMenuView =
                await this.store.menuThreads.QueueJobBatchMenuView.insert();
        });
    }
}

patch(MessagingMenu, {
    template: "queue_job_batch.QueueJobBatchMenuContainer",
    components: {...MessagingMenu.components, QueueJobBatchMenuContainer},
});
