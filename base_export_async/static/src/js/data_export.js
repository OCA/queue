odoo.define("base_export_async.DataExport", function (require) {
    "use strict";

    var core = require("web.core");
    var DataExport = require("web.DataExport");
    var framework = require("web.framework");
    var pyUtils = require("web.py_utils");
    var Dialog = require("web.Dialog");
    var _t = core._t;

    DataExport.include({
        /*
            Overwritten Object responsible for the standard export.
            A flag (checkbox) Async is added and if checked, call the
            delay export instead of the standard export.
        */
        start: function () {
            this._super.apply(this, arguments);
            this.async = this.$("#async_export");
        },
        _exportData(exportedFields, exportFormat, idsToExport) {
            if (this.async && this.async.is(":checked")) {
                /*
                    Checks from the standard method
                */
                if (_.isEmpty(exportedFields)) {
                    Dialog.alert(this, _t("Please select fields to export..."));
                    return;
                }
                if (this.isCompatibleMode) {
                    exportedFields.unshift({name: "id", label: _t("External ID")});
                }

                /*
                    Call the delay export if Async is checked
                */
                framework.blockUI();
                this._rpc({
                    model: "delay.export",
                    method: "delay_export",
                    args: [
                        {
                            data: JSON.stringify({
                                format: exportFormat,
                                model: this.record.model,
                                fields: exportedFields,
                                ids: idsToExport,
                                domain: this.domain,
                                context: pyUtils.eval("contexts", [
                                    this.record.getContext(),
                                ]),
                                import_compat: this.isCompatibleMode,
                                user_ids: [this.record.context.uid],
                            }),
                        },
                    ],
                }).then(function () {
                    framework.unblockUI();
                    Dialog.alert(
                        this,
                        _t(
                            "You will receive the export file by email as soon as it is finished."
                        )
                    );
                });
            } else {
                /*
                    Call the standard method if Async is not checked
                */
                this._super.apply(this, arguments);
            }
        },
    });
});
