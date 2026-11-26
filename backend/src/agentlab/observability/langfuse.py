
"""Centralized Langfuse client management."""

from langfuse import Langfuse, get_client


def get_langfuse_client() -> Langfuse:
    """Return the shared Langfuse client."""
    return get_client()


def shutdown_langfuse_client(client: Langfuse) -> None:
    """Flush pending events and release client resources."""
    try:
        client.flush()
    finally:
        client.shutdown()
