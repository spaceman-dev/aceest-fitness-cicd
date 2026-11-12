"""Request metrics for Prometheus and the fault switch used in rollback drills."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from flask import Flask, Response, current_app, g, jsonify, request

log = logging.getLogger(__name__)

FAULTS = ("unhealthy", "errors")


def _label(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


class RequestMetrics:
    """Per-process counters; each pod runs one gunicorn worker, so one set per pod."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[tuple[str, str, str], int] = {}
        self._seconds = 0.0
        self._count = 0

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        key = (method, route, str(status))
        with self._lock:
            self._requests[key] = self._requests.get(key, 0) + 1
            self._seconds += seconds
            self._count += 1

    def render(self, version: str, track: str) -> str:
        with self._lock:
            requests = sorted(self._requests.items())
            seconds, count = self._seconds, self._count
        lines = [
            "# HELP aceest_build_info Build serving this pod",
            "# TYPE aceest_build_info gauge",
            f'aceest_build_info{{version="{_label(version)}",track="{_label(track)}"}} 1',
            "# HELP aceest_http_requests_total Requests handled, by method, route and status",
            "# TYPE aceest_http_requests_total counter",
        ]
        lines += [
            "aceest_http_requests_total"
            f'{{method="{_label(m)}",route="{_label(r)}",status="{s}"}} {n}'
            for (m, r, s), n in requests
        ]
        lines += [
            "# HELP aceest_http_request_duration_seconds Time spent handling requests",
            "# TYPE aceest_http_request_duration_seconds summary",
            f"aceest_http_request_duration_seconds_sum {seconds:.6f}",
            f"aceest_http_request_duration_seconds_count {count}",
        ]
        return "\n".join(lines) + "\n"


def init_app(app: Flask) -> None:
    metrics = RequestMetrics()
    app.extensions["aceest_metrics"] = metrics

    @app.before_request
    def start_timer() -> None:
        g.request_started = time.perf_counter()

    @app.after_request
    def record(response):
        started = g.pop("request_started", None)
        if started is not None:
            route = request.url_rule.rule if request.url_rule else "unmatched"
            metrics.observe(request.method, route, response.status_code,
                            time.perf_counter() - started)
        return response

    @app.get("/metrics")
    def prometheus_metrics() -> Any:
        from . import __version__

        return Response(metrics.render(__version__, current_app.config["TRACK"]),
                        mimetype="text/plain; version=0.0.4")

    fault = app.config.get("FAULT", "")
    if fault:
        _install_fault(app, fault)


def _install_fault(app: Flask, fault: str) -> None:
    """Rollback drills: start a build that is deliberately broken.

    unhealthy - /api/health answers 503, so readiness fails and the rollout stalls
    errors     - health stays green but the rest of the API answers 500, which
                 only the post-deployment smoke tests catch
    """
    if fault not in FAULTS:
        raise ValueError(f"unknown ACEEST_FAULT '{fault}', expected one of {FAULTS}")
    log.warning("fault injection active: %s", fault)

    @app.before_request
    def injected_fault() -> Any:
        if fault == "unhealthy" and request.path == "/api/health":
            return jsonify({"status": "unhealthy", "fault": fault}), 503
        if fault == "errors" and request.path.startswith("/api/") and request.path != "/api/health":
            return jsonify({"error": "InjectedFault", "message": "fault injection: errors"}), 500
        return None
