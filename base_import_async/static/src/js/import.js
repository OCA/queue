openerp.base_import_async = function (instance) {

    var QWeb = instance.web.qweb;
    var _t = instance.web._t;

    instance.web.DataImport.include({

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
};
