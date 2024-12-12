"""Integration push states api."""

import asyncio
from http import HTTPStatus
from typing import Any

from aiohttp import web

from homeassistant.core import async_get_hass
from homeassistant.helpers.http import HomeAssistantView

from ..const import DOMAIN, LOGGER
from . import service as api_service
from ..push_data_storage.pushdatastorage import PUSHDATA_STORAGE


class DomikaAPIPushStatesWithDelay(HomeAssistantView):
    """Push state with delay endpoint."""

    url = "/domika/push_states_with_delay"
    name = "domika:push-states-with-delay"

    async def post(self, request: web.Request) -> web.Response:
        """Post method."""
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

        entity_id = request_dict.get("entity_id")
        delay = float(request_dict.get("delay", 0))
        ignore_need_push = request_dict.get("ignore_need_push", False)
        need_push = None if ignore_need_push else True

        LOGGER.debug(
            "DomikaAPIPushStatesWithDelay: request_dict: %s, app_session_id: %s",
            request_dict,
            app_session_id,
        )

        await asyncio.sleep(delay)

        PUSHDATA_STORAGE.remove_by_app_session_id(app_session_id=app_session_id, entity_id=entity_id)

        result = await api_service.get(
            app_session_id,
            need_push=need_push,
            entity_id=entity_id,
        )

        data = {"entities": result}
        LOGGER.debug("DomikaAPIPushStatesWithDelay data: %s", data)

        return self.json(data, HTTPStatus.OK)
