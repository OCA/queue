/* @odoo-module */
/* global vis */

import {Component, onMounted, onWillStart, useRef, useState} from "@odoo/owl";
import {loadCSS, loadJS} from "@web/core/assets";

import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {useRecordObserver} from "@web/model/relational_model/utils";
import {useService} from "@web/core/utils/hooks";

export class JobDirectGraph extends Component {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        this.rootRef = useRef("root_vis");
        this.network = null;
        this.state = useState({});

        onWillStart(async () => {
            await loadJS("/queue_job/static/lib/vis/vis-network.min.js");
            loadCSS("/queue_job/static/lib/vis/vis-network.min.css");
        });
        useRecordObserver((record) => {
            this.state.value = record.data[this.props.name];
        });
        onMounted(() => {
            this.renderNetwork();
            this._fitNetwork();
        });
    }

    get $el() {
        return $(this.rootRef.el);
    }

    get resId() {
        return this.props.record.data.id;
    }

    get context() {
        return this.props.record.getFieldContext(this.props.name);
    }

    get model() {
        return this.props.record.resModel;
    }

    htmlTitle(html) {
        const container = document.createElement("div");
        container.innerHTML = html;
        return container;
    }

    renderNetwork() {
        if (this.network) {
            this.$el.empty();
        }

        const nodes = (this.state.value.nodes || []).map((node) => {
            node.title = this.htmlTitle(node.title || "");
            node.label = _t("Job %(id)s", {id: node.id});
            return node;
        });

        const edges = (this.state.value.edges || []).map((edge) => {
            const edgeFrom = edge[0];
            const edgeTo = edge[1];
            return {
                from: edgeFrom,
                to: edgeTo,
                arrows: "to",
            };
        });

        const data = {
            nodes: new vis.DataSet(nodes),
            edges: new vis.DataSet(edges),
        };
        const options = {
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
        const network = new vis.Network(this.$el[0], data, options);
        network.selectNodes([this.resId]);
        network.on("dragging", () => {
            // By default, dragging changes the selected node
            // to the dragged one, we want to keep the current
            // job selected
            network.selectNodes([this.resId]);
        });
        network.on("click", (params) => {
            if (params.nodes.length > 0) {
                const resId = params.nodes[0];
                if (resId !== this.resId) {
                    this.openDependencyJob(resId);
                }
            } else {
                // Clicked outside of the nodes, we want to
                // keep the current job selected
                network.selectNodes([this.resId]);
            }
        });
        this.network = network;
    }

    async openDependencyJob(resId) {
        const action = await this.orm.call(
            this.model,
            "get_formview_action",
            [[resId]],
            {
                context: this.context,
            }
        );
        await this.action.doAction(action);
    }

    _fitNetwork() {
        if (this.network) {
            this.network.fit(this.network.body.nodeIndices);
        }
    }
}

JobDirectGraph.props = {
    ...standardFieldProps,
};

JobDirectGraph.template = "queue.JobDirectGraph";

export const jobDirectGraph = {
    component: JobDirectGraph,
};

registry.category("fields").add("job_directed_graph", jobDirectGraph);
