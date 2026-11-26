
"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentlab.api.routes.observability import router as observability_router
from agentlab.observability.langfuse import (
    get_langfuse_client,
    shutdown_langfuse_client,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application resources."""

    app.state.langfuse = None

    try:
        app.state.langfuse = get_langfuse_client()
        logger.info("Langfuse client initialized.")
    except Exception:
        logger.exception("Failed to initialize Langfuse client.")

    try:
        yield
    finally:
        client = app.state.langfuse

        if client is not None:
            try:
                shutdown_langfuse_client(client)
                logger.info("Langfuse client shut down.")
            except Exception:
                logger.exception("Error shutting down Langfuse client.")


app = FastAPI(
    title="Agentic AI Engineering Lab",
    description="Backend API for the Agentic AI Engineering Lab.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(observability_router)


@app.get("/", tags=["System"])
async def root() -> dict[str, str]:
    return {
        "name": "Agentic AI Engineering Lab",
        "status": "running",
        "message": "Backend API is operational.",
    }


@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    return {
        "status": "healthy",
    }
