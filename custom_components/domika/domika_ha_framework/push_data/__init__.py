"""Push data module."""

import asyncio
import contextlib
import datetime
import uuid

from ..database import core as database_core
from ..utils import chunks
from . import service as push_data_service
from .models import DomikaPushDataCreate

events_queue = asyncio.Queue(maxsize=5000)
confirmed_events_queue = asyncio.Queue(maxsize=5000)

_push_data_processor: set[asyncio.Task] = set()
_push_data_processor_finished = asyncio.Event()

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

    # Store events.
    async with database_core.get_session() as db_session:
        for chunk in chunks(events_to_push, store_chunk_size):
            try:
                await push_data_service.create(db_session, list(chunk))
            except Exception as e:
                print(e)


async def _process_pushed_data(
    events_queue_: asyncio.Queue[DomikaPushDataCreate],
    confirmed_events_queue_: asyncio.Queue[uuid.UUID],
    interval: float,
    threshold: int,
    store_chunk_size: int,
):
    while True:
        task = asyncio.create_task(
            _process_pushed_data_once(
                events_queue_,
                confirmed_events_queue_,
                threshold,
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


def _done_cb(task: asyncio.Task):
    _push_data_processor.discard(task)
    _push_data_processor_finished.set()


def start_push_data_processor(
    interval: float = INTERVAL,
    threshold: int = THRESHOLD,
    store_chunk_size: int = STORE_CHUNK_SIZE,
):
    """
    Start new push data processor task.

    Do nothing if already started.

    Args:
        interval: seconds between checks. Defaults to INTERVAL.
        threshold: minimal time in seconds to wait event confirmation. Defaults to
            THRESHOLD.
        store_chunk_size: size of chunk to store events in database. Defaults to
            STORE_CHUNK_SIZE.
    """
    if _push_data_processor:
        return

    _push_data_processor_finished.clear()

    task = asyncio.create_task(
        _process_pushed_data(
            events_queue,
            confirmed_events_queue,
            interval,
            int(threshold * 1e6),
            store_chunk_size,
        ),
    )
    _push_data_processor.add(task)
    task.add_done_callback(_done_cb)


async def stop_push_data_processor():
    """
    Cancel push data processor task.

    Do nothing if there is no running push data processor task.
    """
    push_data_processor = next(iter(_push_data_processor), None)
    if not push_data_processor:
        return

    push_data_processor.cancel()
    await _push_data_processor_finished.wait()
