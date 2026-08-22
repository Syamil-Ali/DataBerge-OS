from __future__ import annotations

from time import perf_counter

from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware

from app import settings

HTTP_REQUESTS = Counter(
    "data_berge_http_requests_total",
    "HTTP requests handled",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "data_berge_http_request_duration_seconds",
    "HTTP request duration",
    ("method", "route"),
)
HTTP_IN_FLIGHT = Gauge(
    "data_berge_http_requests_in_flight",
    "HTTP requests currently in flight",
)
QUEUE_DEPTH = Gauge(
    "data_berge_queue_depth",
    "Jobs waiting in a durable Redis queue",
    ("queue",),
)


def _queue_depth(queue_name: str) -> float:
    if not settings.REDIS_URL:
        return 0
    try:
        from app.services.redis_runtime import redis_client
        return float(redis_client().llen(f"rq:queue:{queue_name}"))
    except Exception:
        return -1


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        started = perf_counter()
        HTTP_IN_FLIGHT.inc()
        try:
            response = await call_next(request)
            route_object = request.scope.get("route")
            route = getattr(route_object, "path", "unmatched")
            HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
            HTTP_DURATION.labels(request.method, route).observe(perf_counter() - started)
            return response
        finally:
            HTTP_IN_FLIGHT.dec()


def configure_telemetry(app: FastAPI) -> None:
    for queue_name in ("reports", "connectors"):
        QUEUE_DEPTH.labels(queue_name).set_function(
            lambda name=queue_name: _queue_depth(name)
        )
    app.add_middleware(MetricsMiddleware)
    app.mount("/metrics", make_asgi_app())
    if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": "data-berge-api"}))
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        )
    )
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
