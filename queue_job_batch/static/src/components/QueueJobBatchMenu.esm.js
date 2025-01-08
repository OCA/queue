/*
    Copyright 2025 Camptocamp SA (https://www.camptocamp.com).
    License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
*/

import {Component, useState} from "@odoo/owl";
import {ColumnProgress} from "@web/views/view_components/column_progress";
import {Dropdown} from "@web/core/dropdown/dropdown";
import {registry} from "@web/core/registry";
import {useDiscussSystray} from "@mail/utils/common/hooks";
import {useDropdownState} from "@web/core/dropdown/dropdown_hooks";
import {useService} from "@web/core/utils/hooks";
import {user} from "@web/core/user";
import {_t} from "@web/core/l10n/translation";

export class QueueJobBatchMenu extends Component {
    static template = "queue_job_batch.QueueJobBatchMenu";
    static components = {Dropdown, ColumnProgress};
    static props = [];

    /**
     * @override
     */
    setup() {
        super.setup();
        this.discussSystray = useDiscussSystray();
        this.store = useState(useService("mail.store"));
        this.action = useService("action");
        this.userId = user.userId;
        this.ui = useState(useService("ui"));
        this.dropdown = useDropdownState();
    }

    onBeforeOpen() {
        this.store.fetchData({systray_get_queue_job_batches: true});
    }

    getGroupInfo(batch) {
        const types = {
            planned: {
                label: _t("Planned"),
                color: "warning",
                value:
                    batch.job_count -
                    (batch.finished_job_count + batch.failed_job_count),
            },
            finished: {
                label: _t("Finished"),
                color: "success",
                value: batch.finished_job_count,
            },
            failed: {
                label: _t("Failed"),
                color: "danger",
                value: batch.failed_job_count,
            },
        };
        // Build progress bar data
        const progressBar = {bars: []};
        for (const [value, count] of Object.entries(types)) {
            if (count.value) {
                progressBar.bars.push({
                    count: count.value,
                    value,
                    string: types[value].label,
                    color: count.color,
                });
            }
        }
        return {
            aggregate: {
                title: _t("Total"),
                value: batch.job_count,
            },
            count: batch.job_count,
            progressBar,
        };
    }

    openMyJobBatches() {
        this.dropdown.close();
        this.action.doAction("queue_job_batch.action_view_your_queue_job_batch", {
            clearBreadcrumbs: true,
        });
    }

    async onClickItem(ev, batch) {
        ev.preventDefault();
        ev.stopPropagation();
        this.dropdown.close();
        return batch.open();
    }

    async onClickMarkAsRead(ev, batch) {
        ev.preventDefault();
        ev.stopPropagation();
        return batch.markAsRead();
    }
}

registry
    .category("systray")
    .add(
        "queue_job_batch.QueueJobBatchMenu",
        {Component: QueueJobBatchMenu},
        {sequence: 90}
    );
