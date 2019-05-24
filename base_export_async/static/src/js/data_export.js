odoo.define('base_export_async.DataExport', function(require) {
    "use strict";

    var core = require('web.core');
    var DataExport = require('web.DataExport');
    var framework = require('web.framework');
    var pyUtils = require('web.py_utils');
    var Dialog = require('web.Dialog');
    var _t = core._t;

    DataExport.include({
        /*
            Overwritten Object responsible for the standard export.
            A flag (checkbox) Async is added and if checked, call the
            delay export instead of the standard export.
        */
        start: function() {
            this._super.apply(this, arguments);
            this.async = this.$('#async_export');
        },
        export_data: function() {
            var self = this;
            if (self.async.is(":checked")) {
                /*
                    Checks from the standard method
                */
                var exported_fields = this.$(
                    '.o_fields_list option').map(
                    function() {
                        return {
                            name: (self.records[this.value] ||
                                this).value,
                            label: this.textContent ||
                                this.innerText
                        };
                    }).get();

                if (_.isEmpty(exported_fields)) {
                    Dialog.alert(this, _t(
                        "Please select fields to export..."
                    ));
                    return;
                }
                if (!this.isCompatibleMode) {
                    exported_fields.unshift({
                        name: 'id',
                        label: _t('External ID')
                    });
                }

                var export_format = this.$export_format_inputs
                    .filter(':checked').val();

                /*
                    Call the delay export if Async is checked
                */
                framework.blockUI();
                this._rpc({
                    model: 'delay.export',
                    method: 'delay_export',
                    args: [{
                        data: JSON.stringify({
                            format: export_format,
                            model: this
                                .record
                                .model,
                            fields: exported_fields,
                            ids: this
                                .ids_to_export,
                            domain: this
                                .domain,
                            context: pyUtils
                                .eval(
                                    'contexts', [
                                        this
                                        .record
                                        .getContext()
                                    ]
                                ),
                            import_compat:
                                !!
                                this
                                .$import_compat_radios
                                .filter(
                                    ':checked'
                                ).val(),
                        })
                    }],
                }).then(function(result) {
                    framework.unblockUI();
                    Dialog.alert(this, _t(
                        "You will receive the export file by email as soon as it is finished."
                    ));
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
