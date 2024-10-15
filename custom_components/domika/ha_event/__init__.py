"""HA event."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ..const import LOGGER, PUSH_INTERVAL
from ..ha_event import flow as ha_event_flow

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def event_pusher(hass: HomeAssistant) -> None:
    """
    Start new event pusher loop.

    Push registered events to the domika push server.

    Args:
        hass: Homeassistant object.
    """
    LOGGER.debug("Event pusher started")
    try:
        while True:
            await asyncio.sleep(PUSH_INTERVAL.seconds)
            try:
                await ha_event_flow.push_registered_events(hass)
            except Exception:  # noqa: BLE001
                LOGGER.exception("Event pusher error")
    except asyncio.CancelledError as e:
        LOGGER.debug("Event pusher stopped. %s", e)
        raise
