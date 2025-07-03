"""Domika entity router."""

from typing import Any, cast

import voluptuous as vol

from homeassistant.components.websocket_api import (
    ActiveConnection,
    async_response,
    websocket_command,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import update
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.core import State


from ..domika_logger import LOGGER
from ..utils import flatten_json
from .service import get, get_single


@websocket_command(
    {
        vol.Required("type"): "domika/entity_list",
        vol.Required("domains"): list[str],
    },
)
@callback
def websocket_domika_entity_list(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika entity_list request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "entity_list", msg_id is missing')
        return

    LOGGER.verbose('Got websocket message "entity_list", data: %s', msg)

    domains_list = cast(list[str], msg.get("domains"))
    entities = get(hass, domains_list, True)
    result = entities.to_dict()

    connection.send_result(msg_id, result)
    LOGGER.trace("Entity_list msg_id=%s", msg_id)


@websocket_command(
    {
        vol.Required("type"): "domika/entity_info",
        vol.Required("entity_id"): str,
    },
)
@callback
def websocket_domika_entity_info(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika entity_info request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "entity_info", msg_id is missing')
        return

    LOGGER.verbose('Got websocket message "entity_info", data: %s', msg)

    entity_id = cast(str, msg.get("entity_id"))
    entity = get_single(hass, entity_id)
    result = entity.to_dict() if entity else {}

    connection.send_result(msg_id, result)
    LOGGER.trace("Entity_info msg_id=%s data=%s", msg_id, result)


@websocket_command(
    {
        vol.Required("type"): "domika/entity_state",
        vol.Required("entity_id"): str,
    },
)
@async_response
async def websocket_domika_entity_state(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika entity_state request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "entity_state", msg_id is missing')
        return

    LOGGER.verbose('Got websocket message "entity_state", data: %s', msg)

    entity_id = cast(str, msg.get("entity_id"))
    state = hass.states.get(entity_id)
    result: tuple[dict, ...] = ({},)
    if state:
        time_updated = max(state.last_changed, state.last_updated)
        result = (
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
        LOGGER.debug("Entity_state requesting state of unknown entity: %s", entity_id)

    connection.send_result(msg_id, result)
    LOGGER.trace("Entity_state msg_id=%s data=%s", msg_id, result)


@websocket_command(
    {
        vol.Required("type"): "domika/available_updates",
    },
)
@async_response
async def websocket_domika_available_updates(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika available_updates request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "available_updates", msg_id is missing')
        return

    LOGGER.verbose('Got websocket message "available_updates"')

    entity_ids = hass.states.async_entity_ids(update.DOMAIN)
    # LOGGER.verbose("Available_updates: %s", entity_ids)
    entity_registry = er.async_get(hass)

    result = {}

    for entity_id in entity_ids:
        entity: RegistryEntry | None = entity_registry.entities.get(entity_id)
        if not entity or entity.hidden_by or entity.disabled_by:
            continue

        update_state: State | None = hass.states.get(entity_id)
        if not update_state or update_state.state != "on":
            continue

        attr_dict = {}
        for attr, value in update_state.attributes.items():
            attr_dict[attr] = f"{value}"

        result[entity_id] = attr_dict

    connection.send_result(msg_id, result)
    LOGGER.trace("Available_updates msg_id=%s data=%s", msg_id, result)