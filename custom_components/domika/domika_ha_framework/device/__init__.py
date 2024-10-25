"""Application device module."""

from __future__ import annotations

import asyncio

from custom_components.domika.const import (
    DEVICE_INACTIVITY_CHECK_INTERVAL,
    DEVICE_INACTIVITY_TIME_THRESHOLD,
    LOGGER,
)

from ..database import core as database_core
from ..errors import DatabaseError
from . import service as device_service


async def inactive_device_cleaner() -> None:
    """
    Start new inactive device cleaner loop.

    Periodically removes outdated devices.
    """
    LOGGER.debug("Inactive device cleaner started")
    try:
        while True:
            try:
                async with database_core.get_session() as session:
                    await device_service.delete_inactive(
                        session,
                        DEVICE_INACTIVITY_TIME_THRESHOLD,
                    )
            except DatabaseError as e:
                LOGGER.error("Inactive device cleaner database error. %s", e)
            except Exception:  # noqa: BLE001
                LOGGER.exception("Inactive device cleaner error")
            await asyncio.sleep(DEVICE_INACTIVITY_CHECK_INTERVAL.total_seconds())
    except asyncio.CancelledError as e:
        LOGGER.debug("Inactive device cleaner stopped. %s", e)
        raise
