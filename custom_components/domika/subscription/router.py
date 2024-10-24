"""Subscription data router."""

from typing import Any, cast
import uuid

import voluptuous as vol

from homeassistant.components.websocket_api import (
    ActiveConnection,
    async_response,
    websocket_command,
)
from homeassistant.core import HomeAssistant

from ..const import LOGGER
from ..domika_ha_framework.database import core as database_core
from ..domika_ha_framework.errors import DomikaFrameworkBaseError
from ..domika_ha_framework.subscription import flow as subscription_flow
from ..domika_ha_framework.utils import flatten_json
from ..domika_ha_framework.push_data import service as push_data_service


@websocket_command(
    {
        vol.Required("type"): "domika/resubscribe",
        vol.Required("app_session_id"): vol.Coerce(uuid.UUID),
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

    LOGGER.debug('Got websocket message "resubscribe", data: %s', msg)
    app_session_id = cast(uuid.UUID, msg.get("app_session_id"))

    res_list = []
    subscriptions = cast(dict[str, dict[str, int]], msg.get("subscriptions"))
    for entity_id in subscriptions:
        state = hass.states.get(entity_id)
        if state:
            time_updated = max(state.last_changed, state.last_updated)
            res_list.append(
                {
                    "entity_id": entity_id,
                    "time_updated": time_updated,
                    "attributes": flatten_json(
                        state.as_compressed_state,
                        exclude={"c", "lc", "lu"},
                    ),
                },
            )
        else:
            LOGGER.error(
                "Websocket_domika_resubscribe requesting state of unknown entity: %s",
                entity_id,
            )
    connection.send_result(msg_id, {"entities": res_list})

    try:
        async with database_core.get_session() as session:
            await subscription_flow.resubscribe(session, app_session_id, subscriptions)
            await push_data_service.delete_for_app_session(
                session,
                app_session_id=app_session_id
    )

    except DomikaFrameworkBaseError as e:
        LOGGER.error('Can\'t resubscribe "%s". Framework error. %s', subscriptions, e)
    except Exception:  # noqa: BLE001
        LOGGER.exception('Can\'t resubscribe "%s". Unhandled error', subscriptions)
