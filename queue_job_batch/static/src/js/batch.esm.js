/** @odoo-module **/

import {one} from "@mail/model/model_field";
import {registerModel} from "@mail/model/model_core";
import session from "web.session";
const {Component} = owl;

registerModel({
    name: "QueueJobBatch",
    modelMethods: {
        convertData(data) {
            return {
                irModel: {
                    id: data.id,
                    name: data.name,
                    job_count: data.job_count,
                    completeness: data.completeness,
                    failed_percentage: data.failed_percentage,
                    finished_job_count: data.finished_job_count,
                    failed_job_count: data.failed_job_count,
                    state: data.state,
                },
            };
        },
    },
    recordMethods: {
        _hideJobBatch: function () {
            var res_id = this.irModel.id;
            this.queueJobBatchMenuView.close();
            this.delete();
            Component.env.services.rpc({
                model: "queue.job.batch",
                method: "set_read",
                args: [res_id],
                kwargs: {
                    context: session.user_context,
                },
            });
        },
        _onQueueJobBatchClick: function () {
            var res_id = this.irModel.id;
            this._hideJobBatch();
            this.env.services.action.doAction({
                type: "ir.actions.act_window",
                name: "Job batches",
                res_model: "queue.job.batch",
                views: [[false, "form"]],
                res_id: res_id,
            });
        },
    },
    fields: {
        queueJobBatchMenuView: one("QueueJobBatchMenuView", {
            identifying: true,
            inverse: "queueJobBatches",
        }),
        irModel: one("ir.model.queuejobbatch", {
            identifying: true,
            inverse: "queueJobBatch",
        }),
    },
});
