"""Application dashboard router."""

from typing import Any, cast

from ..domika_ha_framework.key_value_storage.models import (
    DomikaKeyValueCreate,
    DomikaKeyValueRead,
    KeyValue,
)
from ..domika_ha_framework.key_value_storage import service as key_value_service
from ..domika_ha_framework.database import core as database_core
from ..domika_ha_framework.errors import DomikaFrameworkBaseError
import voluptuous as vol

from homeassistant.components.websocket_api import (
    ActiveConnection,
    async_response,
    websocket_command,
)
from homeassistant.core import HomeAssistant

from ..const import LOGGER


async def _store_value(
    key: str,
    value: str,
    user_id: str,
) -> None:
    try:
        async with database_core.get_session() as session:
            await key_value_service.create_or_update(
                session,
                DomikaKeyValueCreate(
                    user_id=user_id,
                    key=key,
                    value=value,
                ),
            )
    except DomikaFrameworkBaseError as e:
        LOGGER.error(
            'Can\'t update value "%s" for key: %s, user "%s". Framework error. %s',
            value,
            key,
            user_id,
            e,
        )
    except Exception:  # noqa: BLE001
        LOGGER.exception(
            'Can\'t update value "%s" for key: %s, user "%s. Unhandled error',
            value,
            key,
            user_id,
        )


@websocket_command(
    {
        vol.Required("type"): "domika/store_value",
        vol.Required("key"): str,
        vol.Required("value"): str,
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
        'Got websocket message "store_value", user: "%s", key: %s, value: %s',
        connection.user.id,
        msg.get("key"),
        msg.get("value"),
    )

    # Fast send reply.
    connection.send_result(msg_id, {"result": "accepted"})
    LOGGER.debug("store_value msg_id=%s data=%s", msg_id, {"result": "accepted"})

    key: str | None = msg.get("key")
    if key is None:
        LOGGER.error('Got websocket message "store_value", key is missing')
        return

    value: str = msg.get("value", "")
    await _store_value(key, value, connection.user.id)



async def _get_value(
    key: str,
    user_id: str,
) -> str | None:
    try:
        async with database_core.get_session() as session:
            key_value: KeyValue = await key_value_service.get(
                session,
                DomikaKeyValueRead(
                    user_id=user_id,
                    key=key,
                ),
            )
            return key_value.value if key_value else None
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
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika get dashboards request."""
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

    value: str = msg.get("value", "")

    value = await _get_value(key, connection.user.id)
    result = {"value": value} if value else {}

    connection.send_result(msg_id, result)
    LOGGER.debug("get_value msg_id=%s data=%s", msg_id, result)
