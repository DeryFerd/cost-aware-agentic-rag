"""OpenTelemetry distributed tracing integration."""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import Status, StatusCode

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.info("OpenTelemetry not installed. Install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp")

F = TypeVar("F", bound=Callable[..., Any])

tracer: trace.Tracer | None = None


def setup_tracing(
    endpoint: str | None = None,
    service_name: str = "cost-aware-agentic-rag",
    service_version: str = "0.1.0",
) -> None:
    """Initialize OpenTelemetry TracerProvider with OTLP gRPC exporter.

    Args:
        endpoint: OTLP collector endpoint (e.g. "localhost:4317").
                  Falls back to OTEL_EXPORTER_OTLP_ENDPOINT env var.
        service_name: Logical service name for trace grouping.
        service_version: Semantic version of this service.
    """
    global tracer

    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry unavailable – tracing disabled")
        return

    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: service_version,
    })

    provider = TracerProvider(resource=resource)

    exporter_kwargs: dict[str, Any] = {}
    if endpoint:
        exporter_kwargs["endpoint"] = endpoint

    try:
        exporter = OTLPSpanExporter(**exporter_kwargs)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("OTLP span exporter configured")
    except Exception as exc:
        logger.warning("Failed to create OTLP exporter (%s) – traces will only be logged", exc)

    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(service_name, service_version)
    logger.info("Tracing initialised (service=%s v%s)", service_name, service_version)


def instrument(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """Decorator that wraps a function call in an OTel span.

    Usage::

        @instrument("planner_node")
        def planner_node(state):
            ...

    The span records latency automatically.  Extra attributes can be
    passed via *attributes* or added later inside the function body by
    accessing the current span.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if tracer is None:
                return func(*args, **kwargs)

            span_name = name or f"{func.__module__}.{func.__qualname__}"
            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, str(v))

                t0 = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as exc:
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    span.record_exception(exc)
                    raise
                finally:
                    latency_ms = (time.perf_counter() - t0) * 1000
                    span.set_attribute("duration_ms", round(latency_ms, 2))

        return wrapper  # type: ignore[return-value]

    return decorator
