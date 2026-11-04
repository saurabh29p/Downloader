"""In-process publish/subscribe for job updates, streamed to clients as SSE."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

HEARTBEAT_SECONDS = 15.0


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def publish(self, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            if queue.full():  # slow client: drop the oldest event
                queue.get_nowait()
            queue.put_nowait(event)

    async def subscribe(self) -> AsyncGenerator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


def format_sse(event: str, data: Any) -> str:
    payload = json.dumps(data, default=str, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


async def sse_stream(
    bus: EventBus, job_id: str | None = None, heartbeat: float = HEARTBEAT_SECONDS
) -> AsyncGenerator[str]:
    """Yield SSE text for every job event (optionally one job), with heartbeats."""
    yield ": connected\n\n"
    events = bus.subscribe()
    pending: asyncio.Task[dict[str, Any]] | None = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(anext(events))
            done, _ = await asyncio.wait({pending}, timeout=heartbeat)
            if not done:
                yield ": ping\n\n"
                continue
            event = pending.result()
            pending = None
            if job_id is None or event.get("job", {}).get("id") == job_id:
                yield format_sse(event["type"], event["job"])
    finally:
        if pending is not None:
            pending.cancel()
        await events.aclose()
