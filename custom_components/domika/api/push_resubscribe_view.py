"""Integration resubscribe api."""

from http import HTTPStatus
from typing import Any

from aiohttp import web

from homeassistant.components.http import KEY_HASS_USER
from homeassistant.core import async_get_hass
from homeassistant.helpers.http import HomeAssistantView

from ..access import is_foreign_session
from ..const import DOMAIN
from ..domika_logger import LOGGER
from ..storage import APP_SESSIONS_STORAGE


class DomikaAPIPushResubscribeView(HomeAssistantView):
    """View for subscriptions update."""

    url = "/domika/push_resubscribe"
    name = "domika:push-resubscribe"

    async def post(self, request: web.Request) -> web.Response:
        """Post method."""
        LOGGER.verbose("DomikaAPIPushResubscribeView called.")

        # Check that integration still loaded.
        hass = async_get_hass()
        if not hass.data.get(DOMAIN):
            return self.json_message("Route not found.", HTTPStatus.NOT_FOUND)

        request_dict: dict[str, Any] = await request.json()

        app_session_id = request.headers.get("X-App-Session-Id")
        if not app_session_id:
            return self.json_message(
                "Missing X-App-Session-Id.",
                HTTPStatus.UNAUTHORIZED,
            )
        if is_foreign_session(app_session_id, request[KEY_HASS_USER].id):
            return self.json_message(
                "App session belongs to another user.",
                HTTPStatus.UNAUTHORIZED,
            )

        LOGGER.trace(
            "DomikaAPIPushResubscribeView: request_dict: %s, app_session_id: %s",
            request_dict,
            app_session_id,
        )

        subscriptions: dict[str, set[str]] = request_dict.get("subscriptions", {})
        if not subscriptions:
            return self.json_message(
                "Missing or malformed subscriptions.",
                HTTPStatus.UNAUTHORIZED,
            )

        APP_SESSIONS_STORAGE.resubscribe_push(app_session_id, subscriptions)

        data = {"result": "success"}
        LOGGER.fine("DomikaAPIPushResubscribeView data: %s", data)
        return self.json(data, HTTPStatus.OK)
