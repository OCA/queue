odoo.define("queue_job.fields", function (require) {
    "use strict";

    /**
     * This module contains field widgets for the job queue.
     */

    var AbstractField = require("web.AbstractField");
    var core = require("web.core");
    var field_registry = require("web.field_registry");

    var JobDirectedGraph = AbstractField.extend({
        /* global vis */
        className: "o_field_job_directed_graph",
        cssLibs: ["/queue_job/static/lib/vis/vis-network.min.css"],
        jsLibs: ["/queue_job/static/lib/vis/vis-network.min.js"],
        init: function () {
            this._super.apply(this, arguments);
            this.network = null;
            this.tabListenerInstalled = false;
        },
        start: function () {
            var def = this._super();

            core.bus.on(
                "DOM_updated",
                this,
                function () {
                    this._installTabListener();
                }.bind(this)
            );

            return def;
        },
        _fitNetwork: function () {
            if (this.network) {
                this.network.fit(this.network.body.nodeIndices);
            }
        },
        /*
         * Add a listener on tabs if any: when the widget is render inside a tab,
         * it does not view the view. Install a listener that will fit the network
         * graph to show all the nodes when we switch tab.
         */
        _installTabListener: function () {
            if (this.tabListenerInstalled) {
                return;
            }
            this.tabListenerInstalled = true;

            var tab = this.$el.closest("div.tab-pane");
            if (!tab.length) {
                return;
            }
            $('a[href="#' + tab[0].id + '"]').on(
                "shown.bs.tab",
                function () {
                    this._fitNetwork();
                }.bind(this)
            );
        },
        htmlTitle: function (html) {
            const container = document.createElement("div");
            container.innerHTML = html;
            return container;
        },
        _render: function () {
            var self = this;
            this.$el.empty();

            var nodes = this.value.nodes || [];

            if (!nodes.length) {
                return;
            }
            nodes = _.map(nodes, function (node) {
                node.title = self.htmlTitle(node.title || "");
                return node;
            });

            var edges = [];
            _.each(this.value.edges || [], function (edge) {
                var edgeFrom = edge[0];
                var edgeTo = edge[1];
                edges.push({
                    from: edgeFrom,
                    to: edgeTo,
                    arrows: "to",
                });
            });

            var data = {
                nodes: new vis.DataSet(nodes),
                edges: new vis.DataSet(edges),
            };
            var options = {
                // Fix the seed to have always the same result for the same graph
                layout: {randomSeed: 1},
            };
            // Arbitrary threshold, generation becomes very slow at some
            // point, and disabling the stabilization helps to have a fast result.
            // Actually, it stabilizes, but is displayed while stabilizing, rather
            // than showing a blank canvas.
            if (nodes.length > 100) {
                options.physics = {stabilization: false};
            }
            var network = new vis.Network(this.$el[0], data, options);
            network.selectNodes([this.res_id]);

            network.on("dragging", function () {
                // By default, dragging changes the selected node
                // to the dragged one, we want to keep the current
                // job selected
                network.selectNodes([self.res_id]);
            });
            network.on("click", function (params) {
                if (params.nodes.length > 0) {
                    var jobId = params.nodes[0];
                    if (jobId !== self.res_id) {
                        self.openDependencyJob(jobId);
                    }
                } else {
                    // Clicked outside of the nodes, we want to
                    // keep the current job selected
                    network.selectNodes([self.res_id]);
                }
            });
            this.network = network;
        },
        openDependencyJob: function (res_id) {
            var self = this;
            this._rpc({
                model: this.model,
                method: "get_formview_action",
                args: [[res_id]],
                context: this.record.getContext(this.recordParams),
            }).then(function (action) {
                self.trigger_up("do_action", {action: action});
            });
        },
    });

    field_registry.add("job_directed_graph", JobDirectedGraph);

    return {
        JobDirectedGraph: JobDirectedGraph,
    };
});
