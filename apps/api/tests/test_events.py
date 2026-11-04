import asyncio
import contextlib

from anyget.core.events import EventBus, format_sse, sse_stream


def test_format_sse() -> None:
    assert format_sse("job.updated", {"id": "1", "title": "कथा"}) == (
        'event: job.updated\ndata: {"id": "1", "title": "कथा"}\n\n'
    )


async def test_stream_filters_and_heartbeats() -> None:
    bus = EventBus()
    stream = sse_stream(bus, job_id="a", heartbeat=0.05)
    assert await anext(stream) == ": connected\n\n"
    assert await anext(stream) == ": ping\n\n"  # subscribes, then times out
    bus.publish({"type": "job.updated", "job": {"id": "b"}})
    bus.publish({"type": "job.updated", "job": {"id": "a", "state": "done"}})
    text = await asyncio.wait_for(anext(stream), 1)
    assert text.startswith("event: job.updated") and '"id": "a"' in text
    await stream.aclose()
    assert bus.subscriber_count == 0


async def test_closing_while_waiting_does_not_error() -> None:
    bus = EventBus()
    stream = sse_stream(bus, heartbeat=5)
    await anext(stream)
    waiting = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0.01)
    waiting.cancel()  # client disconnects mid-wait
    with contextlib.suppress(asyncio.CancelledError):
        await waiting
    await stream.aclose()
    assert bus.subscriber_count == 0
