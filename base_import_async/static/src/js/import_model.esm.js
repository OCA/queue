/** @odoo-module **/

import {BaseImportModel} from "@base_import/import_model";
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";

patch(BaseImportModel.prototype, {
    get importOptions() {
        const options = super.importOptions;
        const checkbox = document.querySelector("input.oe_import_queue");
        options.use_queue = checkbox ? checkbox.checked : false;
        return options;
    },

    async executeImport(isTest, totalSteps, importProgress) {
        const def = super.executeImport(isTest, totalSteps, importProgress);
        const checkbox = document.querySelector("input.oe_import_queue");
        if (checkbox && checkbox.checked && !isTest) {
            this._addMessage("warning", [
                _t("Your request is being processed"),
                _t("You can check the status of this job in menu 'Queue / Jobs'."),
            ]);
        }
        return def;
    },
});
