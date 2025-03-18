from http import HTTPStatus
from typing import Any, cast

from aiohttp import web

from homeassistant.core import async_get_hass
from homeassistant.helpers.http import HomeAssistantView

from ..const import DOMAIN
from ..domika_logger import LOGGER
from ..utils import flatten_json


class DomikaAPIEntityStateView(HomeAssistantView):
    """Push state with delay endpoint."""

    url = "/domika/entity_state"
    name = "domika:entity_state"

    async def post(self, request: web.Request) -> web.Response:
        """Post method."""
        LOGGER.verbose("DomikaAPIEntityStateView called.")

        # Check that integration still loaded.
        hass = async_get_hass()
        if not hass.data.get(DOMAIN):
            return self.json_message("Route not found.", HTTPStatus.NOT_FOUND)

        request_dict: dict[str, Any] = await request.json()
        LOGGER.trace("DomikaAPIEntityStateView: request_dict: %s", request_dict,)

        entity_id = cast(list[str], request_dict.get("entity_id"))
        state = hass.states.get(entity_id)
        result = flatten_json(state, exclude={"c", "lc", "lu"}) or {}

        LOGGER.fine("DomikaAPIEntityStateView data: %s", result)
        return self.json(result, HTTPStatus.OK)
