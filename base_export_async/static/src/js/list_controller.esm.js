/** @odoo-module **/

import {blockUI, unblockUI} from "web.framework";

import Dialog from "web.Dialog";
import {ListController} from "@web/views/list/list_controller";
import {_t} from "web.core";
import {download} from "@web/core/network/download";
import {patch} from "@web/core/utils/patch";

patch(ListController.prototype, "base_export_async", {
    async downloadExport(fields, import_compat, format, async = false) {
        let ids = false;
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
            exportedFields.unshift({name: "id", label: this.env._t("External ID")});
        }
        if (async) {
            /*
                Call the delay export if Async is checked
            */
            blockUI();
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
            const orm = this.env.services.orm;
            orm.call("delay.export", "delay_export", args).then(function () {
                unblockUI();
                Dialog.alert(
                    this,
                    _t(
                        "You will receive the export file by email as soon as it is finished."
                    )
                );
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
