/** @odoo-module */

import {ExportDataDialog} from "@web/views/view_dialogs/export_data_dialog";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

patch(ExportDataDialog.prototype, {
    setup() {
        super.setup();
        this.state.async = false;
        this.notification = useService("notification");
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
