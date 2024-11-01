"""Push data module."""

import asyncio
import contextlib
import datetime
import uuid

from custom_components.domika.const import LOGGER

from ..database import core as database_core
from ..errors import DatabaseError
from ..utils import chunks
from . import service as push_data_service
from .models import DomikaPushDataCreate

events_queue = asyncio.Queue(maxsize=5000)
confirmed_events_queue = asyncio.Queue(maxsize=5000)

INTERVAL = 5
THRESHOLD = 10
STORE_CHUNK_SIZE = 500


async def _process_pushed_data_once(
    events_queue_: asyncio.Queue[DomikaPushDataCreate],
    confirmed_events_queue_: asyncio.Queue[uuid.UUID],
    threshold: int,
    store_chunk_size: int,
):
    # Get all confirmed events.
    confirmed_events = []
    with contextlib.suppress(asyncio.QueueEmpty):
        while True:
            confirmed_events.append(confirmed_events_queue_.get_nowait())
            confirmed_events_queue_.task_done()

    events_to_push: list[DomikaPushDataCreate] = []
    events_to_requeue: list[DomikaPushDataCreate] = []

    timestamp = int(datetime.datetime.now(datetime.UTC).timestamp() * 1e6)
    with contextlib.suppress(asyncio.QueueEmpty):
        while True:
            event = events_queue_.get_nowait()
            events_queue_.task_done()

            # If event was confirmed - just ignore it.
            if event.event_id in confirmed_events:
                confirmed_events.remove(event.event_id)
                continue

            # If event wait for confirmation more than allowed by threshold - prepare
            # for write to the DB, prepare for requeueing.
            if timestamp - event.timestamp > threshold:
                events_to_push.append(event)
            else:
                events_to_requeue.append(event)

    # Requeue events.
    for event in events_to_requeue:
        # QueueFull should not be raised due to requeued events count is less or equal
        # to previously read count.
        events_queue_.put_nowait(event)

    # Nothing to push - return.
    if not events_to_push:
        return

    # Store events.
    try:
        chunk_count = 0
        event_count = 0
        for chunk in chunks(events_to_push, store_chunk_size):
            chunk_count += 1
            async with database_core.get_session() as db_session:
                events = list(chunk)
                event_count += len(events)
                await push_data_service.create(db_session, events)
        LOGGER.debug(
            "Pushed data added %d events in %d chunks",
            event_count,
            chunk_count,
        )
    except DatabaseError as e:
        LOGGER.error("Pushed data processor database error. %s", e)

        with contextlib.suppress(asyncio.QueueFull):
            # Requeue events.
            for event in events_to_push:
                events_queue_.put_nowait(event)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Pushed data processor error")
        with contextlib.suppress(asyncio.QueueFull):
            # Requeue events.
            for event in events_to_push:
                events_queue_.put_nowait(event)


async def pushed_data_processor(
    events_queue_: asyncio.Queue[DomikaPushDataCreate] = events_queue,
    confirmed_events_queue_: asyncio.Queue[uuid.UUID] = confirmed_events_queue,
    interval: float = INTERVAL,
    threshold: int = THRESHOLD,
    store_chunk_size: int = STORE_CHUNK_SIZE,
) -> None:
    """
    Start new push data processing loop.

    Read events from events_queue_, filter confirmed events, and store remaining events
    in database.

    Args:
        events_queue_: received events queue.
        confirmed_events_queue_: queue of events that have been confirmed by the
            application.
        interval: seconds between checks. Defaults to INTERVAL.
        threshold: minimal time in seconds to wait event confirmation. Defaults to
            THRESHOLD.
        store_chunk_size: size of chunk to store events in database. Defaults to
            STORE_CHUNK_SIZE.
    """
    LOGGER.debug("Pushed data processor started")
    try:
        while True:
            task = asyncio.create_task(
                _process_pushed_data_once(
                    events_queue_,
                    confirmed_events_queue_,
                    int(threshold * 1e6),
                    store_chunk_size,
                ),
            )
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise
            # Wait for events.
            await asyncio.sleep(interval)
    except asyncio.CancelledError as e:
        LOGGER.debug("Pushed data processor stopped. %s", e)
        raise
