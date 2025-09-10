"""Subscription data router."""

from typing import Any, cast
import voluptuous as vol

from homeassistant.components.websocket_api import (
    ActiveConnection,
    async_response,
    websocket_command,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_get_translations

from ..domika_logger import LOGGER
from ..storage import APP_SESSIONS_STORAGE
from ..push_data_storage.pushdatastorage import PUSHDATA_STORAGE
from ..utils import flatten_json


@websocket_command(
    {
        vol.Required("type"): "domika/resubscribe",
        vol.Required("app_session_id"): str,
        vol.Required("subscriptions"): dict[str, set],
    },
)
@async_response
async def websocket_domika_resubscribe(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika resubscribe request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "resubscribe", msg_id is missing')
        return

    app_session_id = msg.get("app_session_id")
    LOGGER.verbose('Got websocket message "resubscribe", msg_id:%s, app_session_id: %s', msg_id, app_session_id)
    LOGGER.fine('Got websocket message "resubscribe", data: %s', msg)

    res_list = []
    subscriptions = cast(dict[str, dict[str, int]], msg.get("subscriptions"))
    for entity_id in subscriptions:
        state = hass.states.get(entity_id)
        if state:
            time_updated = max(state.last_changed, state.last_updated)

            attributes = {
                "entity_id": entity_id,
                "time_updated": time_updated,
                "attributes": flatten_json(
                    state.as_compressed_state,
                    exclude={"c", "lc", "lu"},
                ),
            }

            if entity_id.startswith("binary_sensor."):
                device_class_attribute = attributes["attributes"]["a.device_class"]
                state_value = attributes["attributes"]["s"]
                if device_class_attribute and state_value and (state_value == "on" or state_value == "off"):
                    language = hass.config.language
                    translations = await async_get_translations(hass, language, "entity_component", {"binary_sensor"})
                    translation_key = f"component.binary_sensor.entity_component.{device_class_attribute}.state.{state_value}"
                    try:
                        attributes["attributes"]["a.s_loc"] = translations[translation_key]
                    except:
                        attributes["attributes"]["a.s_loc"] = None

            res_list.append(attributes)
        else:
            LOGGER.debug(
                "Websocket_domika_resubscribe requesting state of unknown entity: %s",
                entity_id,
            )
    res = {"entities": res_list}
    connection.send_result(msg_id, res)
    LOGGER.trace("resubscribe msg_id=%s data=%s", msg_id, res)

    APP_SESSIONS_STORAGE.resubscribe(app_session_id, subscriptions)
    PUSHDATA_STORAGE.remove_by_app_session_id(app_session_id=app_session_id)
