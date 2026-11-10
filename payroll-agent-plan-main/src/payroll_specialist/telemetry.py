"""Agent-run and step-wise OpenTelemetry for Azure Monitor / Application Insights.

PII guard: never put email body, subject, or full employee names into span attributes.
Use ids and category only. Live Metrics / QuickPulse stay suppressed (see main.py).
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Generator, Iterable, Optional

logger = logging.getLogger("payroll-specialist.telemetry")

_TRACER_NAME = "payroll_specialist"
_configured = False
_memory_exporter = None


def _safe_attr_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    # Hard cap to avoid accidental payload dumps
    if len(text) > 128:
        return text[:125] + "..."
    return text


def pii_safe_attributes(**attrs: Any) -> dict[str, Any]:
    """Filter attribute keys/values that must never leave the process."""
    blocked = {
        "body",
        "subject",
        "email_body",
        "email_subject",
        "content",
        "query",
        "message",
        "employee_name",
        "full_name",
        "name",
        "payload",
    }
    out: dict[str, Any] = {}
    for key, value in attrs.items():
        if key.lower() in blocked:
            continue
        if value is None:
            continue
        out[key] = _safe_attr_value(value)
    return out


def configure_telemetry(
    *,
    connection_string: Optional[str] = None,
    use_memory_exporter: bool = False,
) -> Any:
    """Configure tracer provider once. Returns the tracer."""
    global _configured, _memory_exporter

    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    if _configured:
        return trace.get_tracer(_TRACER_NAME)

    resource = Resource.create(
        {
            "service.name": "payroll-specialist-engine",
            "service.namespace": "engageai",
        }
    )
    provider = TracerProvider(resource=resource)

    if use_memory_exporter:
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        _memory_exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(_memory_exporter))
    else:
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        cs = (connection_string or os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")).strip()
        if cs:
            try:
                from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

                exporter = AzureMonitorTraceExporter(connection_string=cs)
                provider.add_span_processor(BatchSpanProcessor(exporter))
            except Exception as exc:
                logger.warning("Azure Monitor trace exporter not configured: %s", exc)
        else:
            logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING unset; traces stay local/no-op.")

    trace.set_tracer_provider(provider)
    _configured = True
    return trace.get_tracer(_TRACER_NAME)


def get_tracer():
    from opentelemetry import trace

    if not _configured:
        # Lazy no-op-friendly setup without Azure export unless already configured
        configure_telemetry(use_memory_exporter=False)
    return trace.get_tracer(_TRACER_NAME)


def get_memory_exporter():
    return _memory_exporter


def reset_telemetry_for_tests() -> None:
    """Reset module state so tests can reconfigure with an in-memory exporter."""
    global _configured, _memory_exporter
    _configured = False
    _memory_exporter = None
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.util._once import Once

    # Allow TracerProvider override in tests (OTEL normally locks the global provider).
    trace._TRACER_PROVIDER_SET_ONCE = Once()
    trace._TRACER_PROVIDER = None
    trace.set_tracer_provider(TracerProvider())
    # Reset again so configure_telemetry can set the real test provider
    trace._TRACER_PROVIDER_SET_ONCE = Once()
    trace._TRACER_PROVIDER = None
    _configured = False


@contextmanager
def agent_run_span(
    *,
    run_id: Optional[str] = None,
    specialist_id: Optional[str] = None,
    mode: str = "unsupported",
    mailbox_id: Optional[str] = None,
    email_count: Optional[int] = None,
) -> Generator[Any, None, None]:
    tracer = get_tracer()
    attrs = pii_safe_attributes(
        run_id=run_id,
        specialist_id=specialist_id,
        mode=mode,
        mailbox_id=mailbox_id,
        email_count=email_count,
    )
    with tracer.start_as_current_span("agent_run", attributes=attrs) as span:
        try:
            yield span
            span.set_attribute("status", "ok")
        except Exception as exc:
            span.set_attribute("status", "error")
            span.set_attribute("error.type", type(exc).__name__)
            span.record_exception(exc)
            raise


@contextmanager
def step_span(
    name: str,
    **attrs: Any,
) -> Generator[Any, None, None]:
    tracer = get_tracer()
    safe = pii_safe_attributes(step_name=name, **attrs)
    with tracer.start_as_current_span(f"step_{name}", attributes=safe) as span:
        try:
            yield span
        except Exception as exc:
            span.set_attribute("error.type", type(exc).__name__)
            span.record_exception(exc)
            raise


def assert_no_pii_in_spans(spans: Iterable[Any]) -> None:
    """Test helper: fail if blocked attribute keys appear on any span."""
    blocked = {"body", "subject", "query", "content", "employee_name", "payload"}
    for span in spans:
        for key in getattr(span, "attributes", {}) or {}:
            if str(key).lower() in blocked:
                raise AssertionError(f"PII-like attribute present on span: {key}")
