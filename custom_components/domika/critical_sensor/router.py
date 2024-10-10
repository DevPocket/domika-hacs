"""Critical sensor router."""

from typing import Any

import voluptuous as vol

from homeassistant.components.websocket_api import (
    ActiveConnection,
    async_response,
    websocket_command,
)
from homeassistant.core import HomeAssistant

from ..const import LOGGER, SMILEY_HIDDEN_IDS_HASH_KEY, SMILEY_HIDDEN_IDS_KEY
from .enums import NotificationType
from .service import get_with_smiley


@websocket_command(
    {
        vol.Required("type"): "domika/critical_sensors",
    },
)
@async_response
async def websocket_domika_critical_sensors(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika critical sensors request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "critical_sensors", msg_id is missing')
        return

    LOGGER.debug('Got websocket message "critical_sensors", data: %s', msg)

    result = await get_with_smiley(
        hass,
        NotificationType.ANY,
        connection.user.id,
        SMILEY_HIDDEN_IDS_KEY,
        SMILEY_HIDDEN_IDS_HASH_KEY,
    )

    connection.send_result(msg_id, result)
    LOGGER.debug("Critical_sensors msg_id=%s data=%s", msg_id, result)
