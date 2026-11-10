"""HTTP: POST /triage/stream — SSE live progress for mailbox triage."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Callable, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

logger = logging.getLogger("payroll-specialist")

TriageRunFn = Callable[..., Any]


def _sse_line(event_type: str, payload: dict[str, Any]) -> bytes:
    data = json.dumps(payload, default=str)
    return f"event: {event_type}\ndata: {data}\n\n".encode("utf-8")


def _build_default_orchestrator() -> Any:
    """Same email graph wiring as Foundry TRIAGE_RUN (graph.create_payroll_graph)."""
    from graph import build_chat_model
    from models import ChangelistBuildResult, ClassificationResult, ValidationResult
    from structured_output import with_structured
    from tools.snowflake_mcp import get_qa_tools
    from triage.email_graph import build_email_processing_graph, run_email_graph
    from triage.orchestrator import TriageOrchestrator

    classifier_model = build_chat_model(disable_streaming=True)
    qa_model = build_chat_model(disable_streaming=True)
    drafter_model = build_chat_model(disable_streaming=False)
    routing_model = build_chat_model(disable_streaming=True)

    qa_tools = get_qa_tools()
    classifier_llm = with_structured(classifier_model, ClassificationResult)
    qa_llm = qa_model.bind_tools(qa_tools) if qa_tools else qa_model
    validation_llm = qa_model.bind_tools(qa_tools) if qa_tools else qa_model
    validation_model = with_structured(qa_model, ValidationResult)
    changelist_llm = qa_model.bind_tools(qa_tools) if qa_tools else qa_model
    changelist_model = with_structured(qa_model, ChangelistBuildResult)

    email_graph = build_email_processing_graph(
        classifier_llm=classifier_llm,
        qa_llm=qa_llm,
        qa_model=qa_model,
        qa_tools=qa_tools,
        drafter_model=drafter_model,
        routing_model=routing_model,
        validation_llm=validation_llm,
        validation_model=validation_model,
        changelist_llm=changelist_llm,
        changelist_model=changelist_model,
    )

    async def process_email_fn(query: str) -> dict:
        return await run_email_graph(email_graph, query)

    return TriageOrchestrator(process_email_fn=process_email_fn)


def make_triage_stream_route(run_fn: Optional[TriageRunFn] = None) -> Callable[[Request], Any]:
    """Build POST /triage/stream (SSE)."""

    async def triage_stream(request: Request) -> Response:
        specialist_id = (request.query_params.get("specialist_id") or "").strip()
        if not specialist_id:
            return JSONResponse({"detail": "specialist_id is required"}, status_code=400)

        mailbox = (request.query_params.get("mailbox") or "").strip() or None

        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_progress(event: dict[str, Any]) -> None:
            # Same-loop: put immediately so events aren't ordered after the sentinel.
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            if running is loop:
                queue.put_nowait(event)
            else:
                loop.call_soon_threadsafe(queue.put_nowait, event)

        async def run_job() -> None:
            try:
                if run_fn is not None:
                    await run_fn(
                        specialist_id=specialist_id,
                        mailbox_id=mailbox,
                        on_progress=on_progress,
                    )
                else:
                    orch = _build_default_orchestrator()
                    await orch.run(
                        specialist_id=specialist_id,
                        mailbox_id=mailbox,
                        on_progress=on_progress,
                    )
            except Exception as exc:
                logger.exception("POST /triage/stream failed")
                await queue.put({"type": "error", "message": str(exc)})
            finally:
                await queue.put(None)

        async def event_source() -> AsyncIterator[bytes]:
            task = asyncio.create_task(run_job())
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    event_type = str(item.get("type") or "message")
                    yield _sse_line(event_type, item)
            finally:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return triage_stream


def mount_triage_stream_route(app: Any, run_fn: Optional[TriageRunFn] = None) -> None:
    """Register POST /triage/stream."""
    app.add_route(
        "/triage/stream",
        make_triage_stream_route(run_fn=run_fn),
        methods=["POST"],
    )
    logger.info("Mounted triage SSE at POST /triage/stream")
