/** @odoo-module **/

import {attr, many} from "@mail/model/model_field";
import {registerModel} from "@mail/model/model_core";

import session from "web.session";

registerModel({
    name: "QueueJobBatchMenuView",
    lifecycleHooks: {
        _created() {
            this.fetchData();
            document.addEventListener("click", this._onClickCaptureGlobal, true);
        },
        _willDelete() {
            document.removeEventListener("click", this._onClickCaptureGlobal, true);
        },
    },
    recordMethods: {
        close() {
            this.update({isOpen: false});
        },
        async fetchData() {
            const data = await this.messaging.rpc({
                model: "queue.job.batch",
                method: "search_read",
                args: [
                    [
                        ["user_id", "=", session.uid],
                        "|",
                        ["state", "in", ["draft", "progress"]],
                        ["is_read", "=", false],
                    ],
                    [
                        "name",
                        "job_count",
                        "completeness",
                        "failed_percentage",
                        "finished_job_count",
                        "failed_job_count",
                        "state",
                    ],
                ],
                kwargs: {context: session.user_context},
            });
            this.update({
                queueJobBatches: data.map((vals) =>
                    this.messaging.models.QueueJobBatch.convertData(vals)
                ),
            });
        },
        /**
         * @param {MouseEvent} ev
         */
        onClickDropdownToggle(ev) {
            ev.preventDefault();
            if (this.isOpen) {
                this.update({isOpen: false});
            } else {
                this.update({isOpen: true});
                this.fetchData();
            }
        },
        /**
         * Closes the menu when clicking outside, if appropriate.
         *
         * @private
         * @param {MouseEvent} ev
         */
        _onClickCaptureGlobal(ev) {
            if (!this.exists()) {
                return;
            }
            if (!this.component || !this.component.root.el) {
                return;
            }
            if (this.component.root.el.contains(ev.target)) {
                return;
            }
            this.close();
        },
        _viewAllQueueJobBatches: function () {
            this.close();
            this.env.services.action.doAction(
                "queue_job_batch.action_view_your_queue_job_batch"
            );
        },
    },
    fields: {
        queueJobBatches: many("QueueJobBatch", {
            sort: [["greater-first", "irModel.id"]],
            inverse: "queueJobBatchMenuView",
        }),
        component: attr(),
        counter: attr({
            compute() {
                return this.queueJobBatches.length;
            },
        }),
        isOpen: attr({
            default: false,
        }),
    },
});
