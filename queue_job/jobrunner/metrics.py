import socket
from http.server import HTTPServer

from prometheus_client import CollectorRegistry, Counter, Gauge, MetricsHandler

_registry = CollectorRegistry()

_channel_label_names = ("channel", "root", "leaf")
channel_capacity = Gauge(
    "queue_job_channel_capacity",
    documentation="Channel Capacity",
    labelnames=_channel_label_names,
    registry=_registry,
)
channel_pending = Gauge(
    "queue_job_channel_pending",
    documentation="Pending jobs in channel",
    labelnames=_channel_label_names,
    registry=_registry,
)
channel_running = Gauge(
    "queue_job_channel_running",
    documentation="Running jobs in channel",
    labelnames=_channel_label_names,
    registry=_registry,
)
channel_failed = Gauge(
    "queue_job_channel_failed",
    documentation="Failed jobs in channel",
    labelnames=_channel_label_names,
    registry=_registry,
)
channel_waiting_dependencies = Gauge(
    "queue_job_channel_waiting_dependencies",
    documentation="Jobs waiting for dependencies in channel",
    labelnames=_channel_label_names,
    registry=_registry,
)

jobs_to_do = Gauge(
    "queue_job_jobs_to_do",
    documentation=(
        "Number of jobs waiting to be done (including running and failed jobs)"
    ),
    registry=_registry,
)
jobs_scheduled_total = Counter(
    "queue_job_jobs_scheduled_total",
    documentation=(
        "Total number of jobs scheduled for execution (asked Odoo to run job)"
    ),
    labelnames=("db",),
    registry=_registry,
)
dead_jobs_requeued_total = Counter(
    "queue_job_dead_jobs_requeued_total",
    documentation=("Total number of dead jobs requeued"),
    labelnames=("db",),
    registry=_registry,
)


def make_metrics_server(bind_addr, port) -> HTTPServer:
    infos = socket.getaddrinfo(
        bind_addr,
        port,
        type=socket.SOCK_STREAM,
        flags=socket.AI_PASSIVE,
    )
    _, _, _, _, sockaddr = next(iter(infos))
    server = HTTPServer(sockaddr, MetricsHandler.factory(_registry))
    server.socket.setblocking(False)
    return server
