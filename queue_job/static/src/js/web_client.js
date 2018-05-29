odoo.define('queue_job.WebClient', function(require) {
"use strict";

var WebClient = require('web.WebClient');
var base_bus = require('bus.bus');
var session = require('web.session');

WebClient.include({
    show_application: function() {
        var result = this._super();
        this.start_polling();
        return result;
    },

    start_polling: function() {
        this.channel_notify = 'notify_queue_job_notify_' + session.uid;
        this.channel_warn = 'notify_queue_job_warn_' + session.uid;
        base_bus.bus.add_channel(this.channel_notify);
        base_bus.bus.add_channel(this.channel_warn);
        base_bus.bus.on('notification', this, this.bus_notification);
        base_bus.bus.start_polling();
    },
    bus_notification: function(notifications) {
        var self = this;
        _.each(notifications, function (notification) {
            var channel = notification[0];
            var message = notification[1];
            if (channel === self.channel_notify) {
                self.on_message_info(message);
            } else if (channel === self.channel_warn) {
                self.on_message_warn(message);
            }
        });
    },
    on_message_info: function(message){
        if(this.notification_manager) {
            this.notification_manager.do_notify(message.title, message.message, message.sticky);
        }
    },
    on_message_warn: function(message){
        if(this.notification_manager) {
            this.notification_manager.do_warn(message.title, message.message, message.sticky);
        }
    }
});

});
