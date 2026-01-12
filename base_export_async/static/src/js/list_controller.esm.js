/** @odoo-module **/

import {AlertDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {ListController} from "@web/views/list/list_controller";
import {_t} from "@web/core/l10n/translation";
import {download} from "@web/core/network/download";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

patch(ListController.prototype, {
    setup() {
        super.setup();
        this.uiService = useService("ui");
        this.orm = useService("orm");
    },
    async downloadExport(fields, import_compat, format, async = false) {
        let ids = false;
        var self = this;
        if (!this.isDomainSelected) {
            const resIds = await this.getSelectedResIds();
            ids = resIds.length > 0 && resIds;
        }
        const exportedFields = fields.map((field) => ({
            name: field.name || field.id,
            label: field.label || field.string,
            store: field.store,
            type: field.field_type || field.type,
        }));
        if (import_compat) {
            exportedFields.unshift({name: "id", label: _t("External ID")});
        }
        if (async) {
            /*
                Call the delay export if Async is checked
            */
            this.uiService.block();
            const args = [
                {
                    data: JSON.stringify({
                        format: format,
                        model: this.model.root.resModel,
                        fields: exportedFields,
                        ids: ids,
                        domain: this.model.root.domain,
                        context: this.props.context,
                        import_compat: import_compat,
                        user_ids: [this.props.context.uid],
                    }),
                },
            ];
            this.orm.call("delay.export", "delay_export", args).then(function () {
                self.uiService.unblock();
                self.model.dialog.add(AlertDialog, {
                    body: _t(
                        "You will receive the export file by email as soon as it is finished."
                    ),
                });
            });
        } else {
            await download({
                data: {
                    data: JSON.stringify({
                        import_compat,
                        context: this.props.context,
                        domain: this.model.root.domain,
                        fields: exportedFields,
                        groupby: this.model.root.groupBy,
                        ids,
                        model: this.model.root.resModel,
                    }),
                },
                url: `/web/export/${format}`,
            });
        }
    },
});
