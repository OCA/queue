odoo.define('queue_job.fields', function (require) {
"use strict";

/**
 * This module contains field widgets for the job queue.
 */

var AbstractField = require('web.AbstractField');
var core = require('web.core');
var framework = require('web.framework');
var field_registry = require('web.field_registry');

var qweb = core.qweb;
var _t = core._t;

var JobDirectedGraph = AbstractField.extend({
    className: "o_field_job_directed_graph",
    cssLibs: [
        '/queue_job/static/lib/vis/vis-network.min.css'
    ],
    jsLibs: [
        '/queue_job/static/lib/vis/vis-network.min.js'
    ],
    _render: function () {
        var self = this;
        this.$el.empty();

        var nodes = [];
        _.each(this.value.nodes || [], function (nodeId){
            nodes.push({id: nodeId, label: nodeId});
        });
        var edges = [];
        _.each(this.value.edges || [], function (edge){
            var edgeFrom = edge[0];
            var edgeTo = edge[1];
            edges.push({
                from: edgeFrom,
                to: edgeTo,
                arrows: 'to'
            });
        });

        var data = {
            nodes: new vis.DataSet(nodes),
            edges: new vis.DataSet(edges)
        };
        var options = {
            // fix the seed to have always the same result for the same graph
            layout: {randomSeed: 1}
        };
        var network = new vis.Network(this.$el[0], data, options);
        network.selectNodes([this.res_id]);

        network.on("dragging", function () {
            // by default, dragging changes the selected node
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
                // clicked outside of the nodes, we want to
                // keep the current job selected
                network.selectNodes([self.res_id]);
            }
        });
    },
    openDependencyJob: function (res_id) {
        var self = this;
        this._rpc({
            model: this.model,
            method: 'get_formview_action',
            args: [[res_id]],
            context: this.record.getContext(this.recordParams),
        })
        .then(function (action) {
            self.trigger_up('do_action', {action: action});
        });
    }
});

field_registry.add('job_directed_graph', JobDirectedGraph);

return {
    JobDirectedGraph: JobDirectedGraph,
};

});
