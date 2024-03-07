odoo.define("queue_job_batch.systray", function (require) {
    "use strict";

    var core = require("web.core");
    var session = require("web.session");
    var SystrayMenu = require("web.SystrayMenu");
    var Widget = require("web.Widget");
    require("bus.BusService");

    var QWeb = core.qweb;

    var QueueJobBatchMenu = Widget.extend({
        template: "queue_job_batch.view.Menu",
        events: {
            click: "_onMenuClick",
            "click .o_mail_preview": "_onQueueJobBatchClick",
            "click .o_view_all_batch_jobs": "_viewAllQueueJobBatches",
            "click .o_queue_job_batch_hide": "_hideJobBatchClick",
        },
        renderElement: function () {
            this._super();
            var self = this;
            session
                .user_has_group("queue_job_batch.group_queue_job_batch_user")
                .then(function (data) {
                    self.manager = data;
                    if (data) {
                        self.do_show();
                    }
                });
        },
        start: function () {
            var self = this;
            session
                .user_has_group("queue_job_batch.group_queue_job_batch_user")
                .then(function (data) {
                    self.manager = data;
                    if (data) {
                        self.$queue_job_batch_preview = self.$(
                            ".o_mail_systray_dropdown_items"
                        );
                        self._updateQueueJobBatchesPreview();
                        var channel = "queue.job.batch";
                        self.call("bus_service", "addChannel", channel);
                        self.call("bus_service", "startPolling");
                        self.call(
                            "bus_service",
                            "onNotification",
                            self,
                            self._updateQueueJobBatchesPreview
                        );
                    }
                });
            return this._super();
        },

        _getQueueJobBatchesData: function () {
            var self = this;

            return self
                ._rpc({
                    model: "queue.job.batch",
                    method: "search_read",
                    args: [
                        [
                            ["user_id", "=", session.uid],
                            "|",
                            ["state", "in", ["draft", "progress"]],
                            ["is_read", "=", false],
                        ],
                        [
                            "name",
                            "job_count",
                            "completeness",
                            "failed_percentage",
                            "finished_job_count",
                            "failed_job_count",
                            "state",
                        ],
                    ],
                    kwargs: {
                        context: session.user_context,
                    },
                })
                .then(function (data) {
                    self.job_batches = data;
                    self.jobBatchesCounter = data.length;
                    self.$(".o_notification_counter").text(self.jobBatchesCounter);
                    self.$el.toggleClass("o_no_notification", !self.jobBatchesCounter);
                });
        },

        _isOpen: function () {
            return this.$el.hasClass("open");
        },

        _updateQueueJobBatchesPreview: function () {
            var self = this;
            self._getQueueJobBatchesData().then(function () {
                self.$queue_job_batch_preview.html(
                    QWeb.render("queue_job_batch.view.Data", {
                        job_batches: self.job_batches,
                    })
                );
            });
        },
        _hideJobBatchClick: function (event) {
            // Hide the batch without navigating to it.
            event.preventDefault();
            event.stopPropagation();
            var queue_job_batch_id = parseInt(
                $(event.currentTarget, 10).data("job-batch-id"),
                10
            );
            this._hideJobBatch(event, queue_job_batch_id);
        },
        _hideJobBatch: function (event, queue_job_batch_id) {
            this._rpc({
                model: "queue.job.batch",
                method: "set_read",
                args: [queue_job_batch_id],
                kwargs: {
                    context: session.user_context,
                },
            });
        },
        _onQueueJobBatchClick: function (event) {
            var queue_job_batch_id = parseInt(
                $(event.currentTarget, 10).data("job-batch-id"),
                10
            );
            this._hideJobBatch(event, queue_job_batch_id);
            this.do_action({
                type: "ir.actions.act_window",
                name: "Job batches",
                res_model: "queue.job.batch",
                views: [[false, "form"]],
                res_id: queue_job_batch_id,
            });
        },
        _viewAllQueueJobBatches: function () {
            this.do_action("queue_job_batch.action_view_your_queue_job_batch");
        },
        _onMenuClick: function () {
            if (!this._isOpen()) {
                this._updateQueueJobBatchesPreview();
            }
        },
    });

    SystrayMenu.Items.push(QueueJobBatchMenu);

    return QueueJobBatchMenu;
});
