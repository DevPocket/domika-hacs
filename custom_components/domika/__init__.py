"""The Domika integration."""

from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import ClientTimeout

from homeassistant.components import websocket_api
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from sqlalchemy.testing import fails
import string
import random

from .api.domain_services_view import DomikaAPIDomainServicesView
from .api.push_resubscribe import DomikaAPIPushResubscribe
from .api.push_states_with_delay import DomikaAPIPushStatesWithDelay
from .const import (
    DB_DIALECT,
    DB_DRIVER,
    DB_NAME,
    DOMAIN,
    LOGGER,
    PUSH_SERVER_TIMEOUT,
    PUSH_SERVER_URL,
    STORAGE_VERSION,
    STORAGE_KEY_USERS,
    HASS_DATA_KEY_USERS,
    USERS_STORE,
    STORAGE_KEY_APP_SESSIONS,
    HASS_DATA_KEY_APP_SESSIONS
)
from .critical_sensor import router as critical_sensor_router
from .device import router as device_router
from .domika_ha_framework import device, push_data
from .domika_ha_framework.database import (
    core as database_core,
    manage as database_manage,
)
from .entity import router as entity_router
from .ha_event import event_pusher, flow as ha_event_flow, router as ha_event_router
from .key_value_storage import router as key_value_router
from .subscription import router as subscription_router

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
    hass.http.register_view(DomikaAPIPushStatesWithDelay)
    hass.http.register_view(DomikaAPIPushResubscribe)

    LOGGER.debug("Component loaded")
    return True


async def load_domika_data(hass: HomeAssistant):
    global USERS_STORE
    USERS_STORE = Store[dict[str, dict]](
        hass, STORAGE_VERSION, STORAGE_KEY_USERS
    )
    if (users_data := await USERS_STORE.async_load()) is None:
        LOGGER.error("---> Can't load data from users_storage")
        users_data: dict[str, dict] = {}
        await USERS_STORE.async_save(users_data)
    else:
        LOGGER.debug("---> Loaded data from users_storage: %s", users_data)
    hass.data[DOMAIN][HASS_DATA_KEY_USERS] = users_data


# async def save_domika_data(hass: HomeAssistant):
#     await hass.data[DOMAIN][HASS_DATA_KEY_USERS].async_save({"key1": "value1", "key2": "value2", })
#     pass


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    LOGGER.debug("Entry loading")

    # Init framework library.
    try:
        database_url = f"{DB_DIALECT}+{DB_DRIVER}:///{hass.config.path()}/{DB_NAME}"
        await database_manage.migrate(database_url)
        await database_core.init_db(database_url)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Can't setup %s entry", DOMAIN)
        return False

    # Update domain's critical_entities from options.
    if not hass.data.get(DOMAIN):
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["critical_entities"] = entry.options.get("critical_entities")
    hass.data[DOMAIN]["entry"] = entry
    hass.data[DOMAIN]["push_server_url"] = PUSH_SERVER_URL
    hass.data[DOMAIN]["push_server_timeout"] = ClientTimeout(total=PUSH_SERVER_TIMEOUT)

    # Load all Domika data using HA Storage. Data is stored at
    #   hass.data[DOMAIN][HASS_DATA_KEY_USERS]
    #   hass.data[DOMAIN][HASS_DATA_KEY_APP_SESSIONS]
    await load_domika_data(hass)

    # Start pushed data processor background task.
    entry.async_create_background_task(
        hass,
        push_data.pushed_data_processor(),
        "pushed_data_processor",
    )

    # Start inactive device cleaner background task.
    entry.async_create_background_task(
        hass,
        device.inactive_device_cleaner(),
        "inactive_device_cleaner",
    )

    # Register Domika WebSocket commands.
    websocket_api.async_register_command(
        hass,
        device_router.websocket_domika_update_app_session,
    )
    websocket_api.async_register_command(
        hass,
        device_router.websocket_domika_remove_app_session,
    )
    websocket_api.async_register_command(
        hass,
        device_router.websocket_domika_update_push_token,
    )
    websocket_api.async_register_command(
        hass,
        device_router.websocket_domika_update_push_session,
    )
    websocket_api.async_register_command(
        hass,
        device_router.websocket_domika_verify_push_session,
    )
    websocket_api.async_register_command(
        hass,
        device_router.websocket_domika_remove_push_session,
    )
    websocket_api.async_register_command(
        hass,
        subscription_router.websocket_domika_resubscribe,
    )
    websocket_api.async_register_command(
        hass,
        ha_event_router.websocket_domika_confirm_events,
    )
    websocket_api.async_register_command(
        hass,
        critical_sensor_router.websocket_domika_critical_sensors,
    )
    websocket_api.async_register_command(
        hass,
        entity_router.websocket_domika_entity_list,
    )
    websocket_api.async_register_command(
        hass,
        entity_router.websocket_domika_entity_info,
    )
    websocket_api.async_register_command(
        hass,
        entity_router.websocket_domika_entity_state,
    )
    websocket_api.async_register_command(
        hass,
        key_value_router.websocket_domika_store_value,
    )
    websocket_api.async_register_command(
        hass,
        key_value_router.websocket_domika_get_value,
    )
    websocket_api.async_register_command(
        hass,
        key_value_router.websocket_domika_get_value_hash,
    )

    # Register config update callback.
    entry.async_on_unload(entry.add_update_listener(config_update_listener))

    # Register homeassistant startup callback.
    async_at_started(hass, _on_homeassistant_started)

    LOGGER.debug("Entry loaded")
    return True


async def config_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    random_1 = ''.join(random.choices(string.ascii_uppercase, k=5))
    random_2 = ''.join(random.choices(string.ascii_uppercase, k=7))
    random_3 = ''.join(random.choices(string.ascii_uppercase, k=9))
    hass.data[DOMAIN][HASS_DATA_KEY_USERS][random_1] = {random_2: random_3}
    LOGGER.debug("---> Changed user storage: %s", hass.data[DOMAIN][HASS_DATA_KEY_USERS])
    await USERS_STORE.async_save(hass.data[DOMAIN][HASS_DATA_KEY_USERS])

    # Reload entry.
    await hass.config_entries.async_reload(entry.entry_id)



async def async_unload_entry(hass: HomeAssistant, _entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Entry unloading")
    # Unregister Domika WebSocket commands.
    websocket_api_handlers: dict = hass.data.get(websocket_api.DOMAIN, {})
    websocket_api_handlers.pop("domika/update_app_session", None)
    websocket_api_handlers.pop("domika/remove_app_session", None)
    websocket_api_handlers.pop("domika/update_push_token", None)
    websocket_api_handlers.pop("domika/update_push_session", None)
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

    # Close db.
    await database_core.close_db()

    # Clear hass data.
    hass.data.pop(DOMAIN, None)

    LOGGER.debug("Entry unloaded")
    return True


async def async_remove_entry(hass: HomeAssistant, _entry: ConfigEntry) -> None:
    """Handle removal of a local storage."""
    # Delete database.
    db_path = f"{hass.config.path()}/{DB_NAME}"
    try:
        Path(db_path).unlink()
    except OSError:
        LOGGER.error('Can\'t remove database "%s"', db_path)

    LOGGER.debug("Entry removed")


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

    # Setup Domika event listener.
    hass.data[DOMAIN]["cancel_event_listening"] = hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        partial(ha_event_flow.register_event, hass),
    )
    LOGGER.debug("Subscribed to EVENT_STATE_CHANGED events")
