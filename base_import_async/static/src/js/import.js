odoo.define('base_import_async.import', function (require) {
    "use strict";

    var core = require('web.core');
    var _t = core._t;
    var DataImport = require('base_import.import').DataImport;

    DataImport.include({

        import_options: function () {
            var options = this._super.apply(this, arguments);
            options.use_queue = this.$('input.oe_import_queue').prop('checked');
            return options;
        },

        onimported: function () {
            if (this.$('input.oe_import_queue').prop('checked')) {
                this.do_notify(
                    _t("Your request is being processed"),
                    _t("You can check the status of this job in menu 'Queue / Jobs'.")
                );
                this.exit();
            } else {
                this._super.apply(this, arguments);
            }
        },

    });

});
