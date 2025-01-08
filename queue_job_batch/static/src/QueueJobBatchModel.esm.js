import {Record} from "@mail/core/common/record";
import {_t} from "@web/core/l10n/translation";

export class QueueJobBatch extends Record {
    static id = "id";

    /** @type {Object.<string, QueueJobBatch>} */
    static records = {};

    /** @returns {QueueJobBatch} */
    static get() {
        return super.get(...arguments);
    }

    /** @returns {QueueJobBatch|QueueJobBatch[]} */
    static insert() {
        return super.insert(...arguments);
    }

    /** @type {Number} */
    id;

    /** @type {String} */
    name;

    /** @type {Number} */
    job_count;

    /** @type {Number} */
    completeness;

    /** @type {Number} */
    failed_percentage;

    /** @type {Number} */
    finished_job_count;

    /** @type {Number} */
    failed_job_count;

    /** @type {'pending'|'enqueued'|'progress'|'finished'} */
    state;

    async open() {
        this.store.env.services.action.doAction(
            {
                type: "ir.actions.act_window",
                name: _t("Job Batch"),
                res_model: "queue.job.batch",
                view_mode: "form",
                views: [[false, "form"]],
                res_id: this.id,
                target: "current",
            },
            {
                clearBreadcrumbs: true,
            }
        );
    }

    async markAsRead() {
        await this.store.env.services.orm.silent.call("queue.job.batch", "set_read", [
            [this.id],
        ]);
        this.delete();
    }
}

QueueJobBatch.register();
