"""Application dashboard router."""

import contextlib
from typing import Any, cast
import uuid

from ..domika_ha_framework.key_value_storage.models import (
    DomikaKeyValueCreate,
    DomikaKeyValueRead,
    KeyValue,
)
from ..domika_ha_framework.key_value_storage import service as key_value_service
from ..domika_ha_framework.database import core as database_core
from ..domika_ha_framework.errors import DomikaFrameworkBaseError
from ..domika_ha_framework.device import service as device_service
import voluptuous as vol

from homeassistant.components.websocket_api import (
    ActiveConnection,
    async_response,
    websocket_command,
)
from homeassistant.core import HomeAssistant

from ..const import LOGGER


async def _store_value(
    hass: HomeAssistant,
    key: str,
    value: str,
    value_hash: str,
    user_id: str,
    app_session_id: uuid.UUID | None,
) -> None:
    try:
        async with database_core.get_session() as session:
            await key_value_service.create_or_update(
                session,
                DomikaKeyValueCreate(
                    user_id=user_id,
                    key=key,
                    value=value,
                    hash=value_hash,
                ),
            )
            devices = await device_service.get_by_user_id(session, user_id)

        for device in devices:
            if device.app_session_id != app_session_id:
                hass.bus.async_fire(
                    f"domika_{device.app_session_id}",
                    {
                        "d.type": "key_value_update",
                        "key": key,
                        "hash": value_hash,
                    },
                )

    except DomikaFrameworkBaseError as e:
        LOGGER.error(
            'Can\'t update value for key: %s, user "%s". Framework error. %s',
            key,
            user_id,
            e,
        )
    except Exception:  # noqa: BLE001
        LOGGER.exception(
            'Can\'t update value for key: %s, user "%s. Unhandled error',
            key,
            user_id,
        )


@websocket_command(
    {
        vol.Required("type"): "domika/store_value",
        vol.Required("key"): str,
        vol.Required("value"): str,
        vol.Required("hash"): str,
        vol.Optional("app_session_id"): str,
    },
)
@async_response
async def websocket_domika_store_value(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika request to store value for key."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "store_value", msg_id is missing')
        return

    LOGGER.debug(
        'Got websocket message "store_value", user: "%s", key: %s, hash: %s',
        connection.user.id,
        msg.get("key"),
        msg.get("hash"),
    )

    # Fast send reply.
    connection.send_result(msg_id, {"result": "accepted"})
    LOGGER.debug("store_value msg_id=%s data=%s", msg_id, {"result": "accepted"})

    key: str | None = msg.get("key")
    if key is None:
        LOGGER.error('Got websocket message "store_value", key is missing')
        return

    value: str = msg.get("value", "")
    value_hash: str = msg.get("hash", "")

    app_session_id: uuid.UUID | None = None
    with contextlib.suppress(TypeError):
        app_session_id = uuid.UUID(msg.get("app_session_id"))

    await _store_value(hass, key, value, value_hash, connection.user.id, app_session_id)



async def _get_value(
    key: str,
    user_id: str,
) -> KeyValue | None:
    try:
        async with database_core.get_session() as session:
            key_value = await key_value_service.get(
                session,
                DomikaKeyValueRead(
                    user_id=user_id,
                    key=key,
                )
            )
            return key_value
    except DomikaFrameworkBaseError as e:
        LOGGER.error(
            'Can\'t get value for key: %s, user "%s". Framework error. %s',
            key,
            user_id,
            e,
        )
    except Exception:  # noqa: BLE001
        LOGGER.exception(
            'Can\'t get value for key: %s, user "%s. Unhandled error',
            key,
            user_id,
        )


@websocket_command(
    {
        vol.Required("type"): "domika/get_value",
        vol.Required("key"): str,
    },
)
@async_response
async def websocket_domika_get_value(
    _hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika get value request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "get_value", msg_id is missing')
        return

    LOGGER.debug(
        'Got websocket message "get_value", user: "%s", key: %s',
        connection.user.id,
        msg.get("key"),
    )

    key: str | None = msg.get("key")
    if key is None:
        LOGGER.error('Got websocket message "get_value", key is missing')
        return

    key_value: KeyValue | None = await _get_value(key, connection.user.id)
    result = {"value": key_value.value, "hash": key_value.hash} if key_value else {}

    connection.send_result(msg_id, result)
    LOGGER.debug("get_value msg_id=%s data=%s", msg_id, result)



@websocket_command(
    {
        vol.Required("type"): "domika/get_value_hash",
        vol.Required("key"): str,
    },
)
@async_response
async def websocket_domika_get_value_hash(
    _hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika get value hash request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "get_value_hash", msg_id is missing')
        return

    LOGGER.debug(
        'Got websocket message "get_value_hash", user: "%s", key: %s',
        connection.user.id,
        msg.get("key"),
    )

    key: str | None = msg.get("key")
    if key is None:
        LOGGER.error('Got websocket message "get_value_hash", key is missing')
        return

    key_value: KeyValue | None = await _get_value(key, connection.user.id)
    result = {"hash": key_value.hash} if key_value else {}

    connection.send_result(msg_id, result)
    LOGGER.debug("get_value_hash msg_id=%s data=%s", msg_id, result)