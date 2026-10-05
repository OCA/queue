/* @odoo-module */
/* global vis */

import {loadCSS, loadJS} from "@web/core/assets";

import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

import weUtils from "@web_editor/js/common/utils";

const {Component, onWillStart, useRef, onMounted} = owl;

const {document} = globalThis;

const SERVER_NODE = "server_node";

const CHANNEL_FIELDS = [
    "name",
    "complete_name",
    "parent_id",
    "capacity",
    "effective_capacity",
    "sequential",
    "throttle",
    "paused",
    "effective_paused",
    "capacity_default",
    "sequential_default",
];

class ChannelTree extends Component {
    static template = "queue_job.ChannelTree";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.rootRef = useRef("root_vis");
        this.network = null;

        onWillStart(async () => {
            await Promise.all([
                loadJS("/queue_job/static/lib/vis/vis-network.min.js"),
                loadCSS("/queue_job/static/lib/vis/vis-network.min.css"),
            ]);
            await this.loadChannels();
        });

        onMounted(() => this.renderNetwork());
    }

    get $el() {
        return this.rootRef.el;
    }

    async loadChannels() {
        this.channels = await this.orm.searchRead(
            "queue.job.channel",
            [],
            CHANNEL_FIELDS
        );
    }

    htmlTitle(html) {
        const container = document.createElement("div");
        container.innerHTML = html;
        return container;
    }

    edgeWidth(capacity) {
        if (!capacity) {
            return 1;
        }
        return capacity;
    }

    nodePopup(channel) {
        const rows = [
            [_t("Capacity"), channel.capacity || _t("inherited")],
            [_t("Effective capacity"), channel.effective_capacity],
            [_t("Sequential"), channel.sequential ? _t("yes") : _t("no")],
            [
                _t("Throttle"),
                channel.throttle ? `${channel.throttle}${_t("s")}` : _t("none"),
            ],
            [_t("Default capacity"), channel.capacity_default || _t("inherited")],
            [
                _t("Default sequential"),
                channel.sequential_default ? _t("yes") : _t("no"),
            ],
        ];

        let pausedStatus = "";
        if (channel.paused) {
            pausedStatus = ` (${_t("Paused")})`;
        } else if (channel.effective_paused) {
            pausedStatus = ` (${_t("Paused by parent")})`;
        }
        const headerTitle = `${channel.complete_name}${pausedStatus}`;
        const header = `<div style="margin-bottom: 6px;"><b>${headerTitle}</b></div>`;

        const lines = rows
            .map(([label, value]) => `<div><b>${label}:</b> ${value}</div>`)
            .join("");

        const hints =
            `<div class="text-muted small" style="margin-top: 6px;">` +
            `<div>${_t("Double-click to open the channel")}</div>` +
            `<div>${_t("Right-click to create a subchannel")}</div>` +
            `</div>`;
        return `<div>${header}${lines}${hints}</div>`;
    }

    renderNetwork() {
        if (this.network) {
            this.$el.innerHTML = "";
        }

        const activeColor = weUtils.getCSSVariableValue("teal");
        const pausedColor = weUtils.getCSSVariableValue("orange");

        const nodes = this.channels.map((channel) => ({
            id: channel.id,
            label: channel.name,
            title: this.htmlTitle(this.nodePopup(channel)),
            color: channel.effective_paused ? pausedColor : activeColor,
            // Show root channel larger
            font: channel.parent_id ? undefined : {size: 20},
        }));

        const edges = this.channels
            .filter((channel) => channel.parent_id)
            .map((channel) => ({
                from: channel.parent_id[0],
                to: channel.id,
                width: this.edgeWidth(channel.effective_capacity),
                label: String(channel.effective_capacity),
                title: _t("Effective capacity: %s", channel.effective_capacity),
            }));

        const rootChannel = this.channels.find((channel) => !channel.parent_id);
        if (rootChannel) {
            // Build an invisible node on the left of the root channel to
            // show an outgoing line towards "an exit" (execution by the server)
            nodes.push({
                id: SERVER_NODE,
                label: "",
                color: {background: "transparent", border: "transparent"},
                chosen: false,
            });
            edges.push({
                from: SERVER_NODE,
                to: rootChannel.id,
                width: this.edgeWidth(rootChannel.effective_capacity),
                label: String(rootChannel.effective_capacity),
                title: _t("Server capacity: %s", rootChannel.effective_capacity),
                // The line would be transparent (as the node itself) otherwise
                color: {color: activeColor, inherit: false},
            });
        }

        const data = {
            nodes: new vis.DataSet(nodes),
            edges: new vis.DataSet(edges),
        };

        const options = {
            layout: {
                hierarchical: {
                    direction: "LR",
                    sortMethod: "directed",
                    // Align each channel "level" with the same level (default
                    // is to align leaves on the right (e.g. with root.p1 and
                    // root.p2.foo, shakeTowards: roots aligns p1 with p2,
                    // whereas the defaults aligns p1 with foo)
                    shakeTowards: "roots",
                },
            },
            physics: false,
        };

        const network = new vis.Network(this.$el, data, options);
        network.on("doubleClick", (params) => {
            if (params.nodes.length > 0 && params.nodes[0] !== SERVER_NODE) {
                this.actionOpenChannel(params.nodes[0]);
            }
        });
        network.on("oncontext", (params) => {
            params.event.preventDefault();
            const nodeId = network.getNodeAt(params.pointer.DOM);
            if (nodeId !== undefined && nodeId !== SERVER_NODE) {
                this.actionNewChildChannel(nodeId);
            }
        });

        this.network = network;
    }

    async actionOpenChannel(resId) {
        const action = await this.orm.call("queue.job.channel", "get_formview_action", [
            [resId],
        ]);
        await this.action.doAction(action);
    }

    async actionNewChildChannel(parentId) {
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "queue.job.channel",
                views: [[false, "form"]],
                target: "new",
                context: {default_parent_id: parentId},
            },
            {
                onClose: async () => {
                    await this.loadChannels();
                    this.renderNetwork();
                },
            }
        );
    }
}

registry.category("actions").add("queue_job_channel_tree", ChannelTree);
