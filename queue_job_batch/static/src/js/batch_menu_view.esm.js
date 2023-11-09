/** @odoo-module **/

import {registerMessagingComponent} from "@mail/utils/messaging_component";
import {useComponentToModel} from "@mail/component_hooks/use_component_to_model";

const {Component} = owl;

export class QueueJobBatchMenuView extends Component {
    /**
     * @override
     */
    setup() {
        super.setup();
        useComponentToModel({fieldName: "component"});
    }
    /**
     * @returns {QueueJobBatchMenuView}
     */
    get queueJobBatchMenuView() {
        return this.props.record;
    }
}

Object.assign(QueueJobBatchMenuView, {
    props: {record: Object},
    template: "queue_job_batch.QueueJobBatchMenuView",
});

registerMessagingComponent(QueueJobBatchMenuView);
