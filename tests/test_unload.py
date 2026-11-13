"""Unloading the entry."""

import inspect
from unittest.mock import Mock

from homeassistant.components import websocket_api

import custom_components.domika as domika
from custom_components.domika.critical_sensor import router as critical_sensor_router
from custom_components.domika.entity import router as entity_router
from custom_components.domika.ha_event import router as ha_event_router
from custom_components.domika.key_value import router as key_value_router
from custom_components.domika.sessions import router as sessions_router
from custom_components.domika.subscription import router as subscription_router

ROUTERS = (
    critical_sensor_router,
    entity_router,
    ha_event_router,
    key_value_router,
    sessions_router,
    subscription_router,
)


def _domika_command_handlers() -> list:
    return [
        member
        for router in ROUTERS
        for _, member in inspect.getmembers(router)
        if str(getattr(member, "_ws_command", "")).startswith("domika/")
    ]


async def test_unload_unregisters_every_domika_command():
    handlers = _domika_command_handlers()
    hass = Mock()
    hass.data = {websocket_api.DOMAIN: {h._ws_command: (h, None) for h in handlers}, domika.DOMAIN: {}}

    assert await domika.async_unload_entry(hass, Mock())

    assert hass.data[websocket_api.DOMAIN] == {}


def test_every_domika_command_is_registered():
    assert set(domika.WEBSOCKET_COMMANDS) == set(_domika_command_handlers())
