
"""Observability diagnostic endpoints."""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/observability", tags=["Observability"])


@router.post("/test")
def create_test_trace(request: Request) -> dict[str, str]:
    """Create a test observation in Langfuse."""

    client = getattr(request.app.state, "langfuse", None)

    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Langfuse client is not available.",
        )

    with client.start_as_current_observation(
        as_type="span",
        name="agentlab.langfuse.integration-test",
        input={
            "source": "Agentic AI Engineering Lab",
            "purpose": "Verify Langfuse integration",
        },
        metadata={
            "environment": "development",
            "test": True,
        },
    ) as span:
        trace_id = client.get_current_trace_id()

        span.update(
            output={
                "status": "success",
                "message": "Langfuse integration is working.",
            }
        )

    client.flush()

    return {
        "status": "success",
        "message": "Test trace submitted to Langfuse.",
        "trace_id": trace_id or "unavailable",
    }
