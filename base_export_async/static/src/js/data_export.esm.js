/** @odoo-module */

import {ExportDataDialog} from "@web/views/view_dialogs/export_data_dialog";
import {patch} from "@web/core/utils/patch";

patch(ExportDataDialog.prototype, "base_export_async", {
    setup() {
        this._super();
        this.state.async = false;
    },
    onToggleExportAsync(value) {
        this.state.async = value;
    },
    async onClickExportButton() {
        if (!this.state.exportList.length) {
            return this.notification.add(
                this.env._t("Please select fields to save export list..."),
                {
                    type: "danger",
                }
            );
        }
        await this.props.download(
            this.state.exportList,
            this.state.isCompatible,
            this.availableFormats[this.state.selectedFormat].tag,
            this.state.async
        );
    },
});
