"""The Domika integration."""

from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.auth.permissions.events import SUBSCRIBE_ALLOWLIST
from homeassistant.components import websocket_api
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.start import async_at_started
from .api.domain_services_view import DomikaAPIDomainServicesView
from .api.push_resubscribe_view import DomikaAPIPushResubscribeView
from .api.push_states_with_delay_view import DomikaAPIPushStatesWithDelayView
from .entity.entity_list_view import DomikaAPIEntityListView
from .entity.entity_state_view import DomikaAPIEntityStateView
from .const import (
    DOMAIN,
)
from .domika_logger import LOGGER
from .critical_sensor import router as critical_sensor_router
from .sessions import router as device_router
from .entity import router as entity_router
from .ha_event import event_pusher, flow as ha_event_flow, router as ha_event_router
from .key_value import router as key_value_router
from .storage import init_storage, APP_SESSIONS_STORAGE, USERS_STORAGE
from .subscription import router as subscription_router
from . import push_data_storage

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up component."""
    LOGGER.debug("Component loading")

    # Setup Domika api views.
    hass.http.register_view(DomikaAPIDomainServicesView)
    hass.http.register_view(DomikaAPIPushStatesWithDelayView)
    hass.http.register_view(DomikaAPIPushResubscribeView)

    hass.http.register_view(DomikaAPIEntityListView)
    hass.http.register_view(DomikaAPIEntityStateView)

    LOGGER.verbose("Component loaded")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    LOGGER.debug("Entry loading")

    # Update domain's critical_entities from options.
    if not hass.data.get(DOMAIN):
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["critical_entities"] = entry.options.get("critical_entities")
    hass.data[DOMAIN]["entry"] = entry

    # Init storage.
    await init_storage(hass)

    # Start inactive sessions cleaner background task.
    entry.async_create_background_task(
        hass,
        APP_SESSIONS_STORAGE.inactive_device_cleaner(),
        "inactive_device_cleaner",
    )

    SUBSCRIBE_ALLOWLIST.add("domika_critical_sensors_changed")

    # Register Domika WebSocket commands.
    websocket_api.async_register_command(hass, device_router.websocket_domika_update_app_session,)
    websocket_api.async_register_command(hass,device_router.websocket_domika_remove_app_session,)
    websocket_api.async_register_command(hass,device_router.websocket_domika_update_push_token,)
    websocket_api.async_register_command(hass,device_router.websocket_domika_update_push_session,)
    websocket_api.async_register_command(hass,device_router.websocket_domika_update_push_session_v2,)
    websocket_api.async_register_command(hass,device_router.websocket_domika_verify_push_session,)
    websocket_api.async_register_command(hass,device_router.websocket_domika_remove_push_session,)
    websocket_api.async_register_command(hass,subscription_router.websocket_domika_resubscribe,)
    websocket_api.async_register_command(hass,ha_event_router.websocket_domika_confirm_events,)
    websocket_api.async_register_command(hass,critical_sensor_router.websocket_domika_critical_sensors,)
    websocket_api.async_register_command(hass,entity_router.websocket_domika_entity_list,)
    websocket_api.async_register_command(hass,entity_router.websocket_domika_entity_info,)
    websocket_api.async_register_command(hass,entity_router.websocket_domika_entity_state,)
    websocket_api.async_register_command(hass,entity_router.websocket_domika_available_updates,)
    websocket_api.async_register_command(hass,key_value_router.websocket_domika_store_value,)
    websocket_api.async_register_command(hass,key_value_router.websocket_domika_get_value,)
    websocket_api.async_register_command(hass,key_value_router.websocket_domika_get_value_hash,)

    # Register config update callback.
    entry.async_on_unload(entry.add_update_listener(config_update_listener))

    # Register homeassistant startup callback.
    async_at_started(hass, _on_homeassistant_started)

    LOGGER.verbose("Entry loaded")
    return True


async def config_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    # Reload entry.
    await hass.config_entries.async_reload(entry.entry_id)
    LOGGER.trace("config_update_listener: config options changed")
    critical_sensor_router.send_critical_push_sensors_present_changed_events(hass)


async def async_unload_entry(hass: HomeAssistant, _entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Entry unloading")
    # Unregister Domika WebSocket commands.
    websocket_api_handlers: dict = hass.data.get(websocket_api.DOMAIN, {})
    websocket_api_handlers.pop("domika/update_app_session", None)
    websocket_api_handlers.pop("domika/remove_app_session", None)
    websocket_api_handlers.pop("domika/update_push_token", None)
    websocket_api_handlers.pop("domika/update_push_session", None)
    websocket_api_handlers.pop("domika/update_push_session_v2", None)
    websocket_api_handlers.pop("domika/verify_push_session", None)
    websocket_api_handlers.pop("domika/remove_push_session", None)
    websocket_api_handlers.pop("domika/resubscribe", None)
    websocket_api_handlers.pop("domika/confirm_event", None)
    websocket_api_handlers.pop("domika/critical_sensors", None)
    websocket_api_handlers.pop("domika/entity_list", None)
    websocket_api_handlers.pop("domika/entity_info", None)
    websocket_api_handlers.pop("domika/entity_state", None)
    websocket_api_handlers.pop("domika/store_value", None)
    websocket_api_handlers.pop("domika/get_value", None)
    websocket_api_handlers.pop("domika/get_value_hash", None)

    # Cancel Domika event listening.
    if (domika_data := hass.data.get(DOMAIN)) and (
        cancel_event_listening := domika_data.get("cancel_event_listening")
    ):
        cancel_event_listening()

    await asyncio.sleep(0)

    # Clear hass data.
    hass.data.pop(DOMAIN, None)

    LOGGER.verbose("Entry unloaded")
    return True


async def async_remove_entry(hass: HomeAssistant, _entry: ConfigEntry) -> None:
    """Handle removal of a local storage."""
    LOGGER.debug("Entry removing")
    await APP_SESSIONS_STORAGE.delete_storage()
    await USERS_STORAGE.delete_storage()
    LOGGER.verbose("Entry removed")


async def async_migrate_entry(_hass: HomeAssistant, _entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    return True


async def _on_homeassistant_started(hass: HomeAssistant) -> None:
    """Start listen events and push data after homeassistant fully started."""
    # Setup event pusher.
    entry: ConfigEntry = hass.data[DOMAIN]["entry"]
    entry.async_create_background_task(
        hass,
        event_pusher(hass),
        "event_pusher",
    )
    LOGGER.debug("Started EVENT_PUSHER")

    # Setup Domika event listener.
    hass.data[DOMAIN]["cancel_event_listening"] = hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        partial(ha_event_flow.register_event, hass),
    )
    LOGGER.debug("Subscribed to EVENT_STATE_CHANGED events")
