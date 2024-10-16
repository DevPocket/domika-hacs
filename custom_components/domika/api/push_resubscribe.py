"""Integration resubscribe api."""

from http import HTTPStatus
from typing import Any
import uuid

from aiohttp import web

from homeassistant.core import async_get_hass
from homeassistant.helpers.http import HomeAssistantView

from ..const import DOMAIN, LOGGER
from ..domika_ha_framework.database import core as database_core
from ..domika_ha_framework.errors import DomikaFrameworkBaseError
from ..domika_ha_framework.subscription import flow as subscription_flow


class DomikaAPIPushResubscribe(HomeAssistantView):
    """View for subscriptions update."""

    url = "/domika/push_resubscribe"
    name = "domika:push-resubscribe"

    async def post(self, request: web.Request) -> web.Response:
        """Post method."""
        # Check that integration still loaded.
        hass = async_get_hass()
        if not hass.data.get(DOMAIN):
            return self.json_message("Route not found.", HTTPStatus.NOT_FOUND)

        request_dict: dict[str, Any] = await request.json()

        try:
            app_session_id = uuid.UUID(request.headers.get("X-App-Session-Id"))
        except (TypeError, ValueError):
            return self.json_message(
                "Missing or malformed X-App-Session-Id.",
                HTTPStatus.UNAUTHORIZED,
            )

        LOGGER.debug(
            "DomikaAPIPushResubscribe: request_dict: %s, app_session_id: %s",
            request_dict,
            app_session_id,
        )

        subscriptions: dict[str, set[str]] | None = request_dict.get("subscriptions")
        if not subscriptions:
            return self.json_message(
                "Missing or malformed subscriptions.",
                HTTPStatus.UNAUTHORIZED,
            )

        try:
            async with database_core.get_session() as session:
                await subscription_flow.resubscribe_push(
                    session,
                    app_session_id,
                    subscriptions,
                )
        except DomikaFrameworkBaseError as e:
            LOGGER.error(
                'Can\'t resubscribe push "%s". Framework error. %s',
                subscriptions,
                e,
            )
            return self.json_message(
                "Internal error.",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception(
                'Can\'t resubscribe push "%s". Unhandled error',
                subscriptions,
            )
            return self.json_message(
                "Internal error.",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        data = {"result": "success"}
        LOGGER.debug("DomikaAPIPushResubscribe data: %s", data)
        return self.json(data, HTTPStatus.OK)
