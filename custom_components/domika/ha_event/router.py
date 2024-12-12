"""HA event router."""

from typing import Any, cast
import voluptuous as vol

from homeassistant.components.websocket_api import (
    ActiveConnection,
    async_response,
    websocket_command,
)
from homeassistant.core import HomeAssistant

from ..const import LOGGER
from ..push_data_storage.pushdatastorage import PUSHDATA_STORAGE


@websocket_command(
    {
        vol.Required("type"): "domika/confirm_event",
        vol.Required("app_session_id"): str,
        vol.Required("event_ids"): [str],
    },
)
@async_response
async def websocket_domika_confirm_events(
    _hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika confirm event request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "confirm_event", msg_id is missing')
        return

    LOGGER.debug('Got websocket message "confirm_event", data: %s', msg)

    # Fast send reply.
    connection.send_result(msg_id, {"result": "accepted"})
    LOGGER.debug("Confirm_event msg_id=%s data=%s", msg_id, {"result": "accepted"})

    event_ids = cast(list[str], msg.get("event_ids"))
    app_session_id = msg.get("app_session_id")

    if event_ids and app_session_id:
        PUSHDATA_STORAGE.remove_by_event_ids(app_session_id=app_session_id, event_ids=event_ids)
