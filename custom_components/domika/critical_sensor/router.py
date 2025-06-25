"""Critical sensor router."""

from typing import Any

import voluptuous as vol

from homeassistant.components.websocket_api import (
    ActiveConnection,
    async_response,
    websocket_command,
)
from homeassistant.core import HomeAssistant

from ..storage import APP_SESSIONS_STORAGE
from ..const import SMILEY_HIDDEN_IDS_HASH_KEY, SMILEY_HIDDEN_IDS_KEY
from ..domika_logger import LOGGER
from .enums import NotificationType
from .service import get_with_smiley, critical_push_sensors_present, _send_critical_push_sensors_present_changed_events


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

    LOGGER.verbose('Got websocket message "critical_sensors", data: %s', msg)

    result = await get_with_smiley(
        hass,
        NotificationType.ANY,
        connection.user.id,
        SMILEY_HIDDEN_IDS_KEY,
        SMILEY_HIDDEN_IDS_HASH_KEY,
    )

    connection.send_result(msg_id, result)
    LOGGER.trace("Critical_sensors msg_id=%s data=%s", msg_id, result)


def send_critical_push_sensors_present_changed_events(hass: HomeAssistant):
    sensors_present = critical_push_sensors_present(hass)
    LOGGER.verbose('send_critical_push_sensors_present_changed_events, sensors_present: %s', sensors_present)
    app_session_ids = APP_SESSIONS_STORAGE.get_all_app_sessions()
    LOGGER.verbose('send_critical_push_sensors_present_changed_events, app_session_ids: %s', app_session_ids)
    _send_critical_push_sensors_present_changed_events(hass, sensors_present, app_session_ids)

