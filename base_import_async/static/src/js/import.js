odoo.define('base_import_async.import', function (require) {
    "use strict";

    var core = require('web.core');
    var _t = core._t;
    require('base_import.import');

    var DataImport = core.action_registry.get('import');

    DataImport = DataImport.include({

        import_options: function () {
            var options = this._super.apply(this, arguments);
            options.use_connector = this.$('input.oe_import_connector').prop('checked');
            return options;
        },

        onimported: function () {
            var self = this;
            if (this.$('input.oe_import_connector').prop('checked')) {
                this.do_notify(_t("Your request is being processed"), _t("You can check the status of this job in menu 'Connector / Jobs'."));
            }
            this._super.apply(this, arguments);
        },

    });

});
