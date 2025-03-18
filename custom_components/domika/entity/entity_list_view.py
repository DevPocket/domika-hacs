from http import HTTPStatus
from typing import Any, cast

from aiohttp import web

from homeassistant.core import async_get_hass
from homeassistant.helpers.http import HomeAssistantView

from .service import get
from ..const import DOMAIN
from ..domika_logger import LOGGER

class DomikaAPIEntityListView(HomeAssistantView):
    """Push state with delay endpoint."""

    url = "/domika/entity_list"
    name = "domika:entity_list"

    async def post(self, request: web.Request) -> web.Response:
        """Post method."""
        LOGGER.verbose("DomikaAPIEntityListView called.")

        # Check that integration still loaded.
        hass = async_get_hass()
        if not hass.data.get(DOMAIN):
            return self.json_message("Route not found.", HTTPStatus.NOT_FOUND)

        request_dict: dict[str, Any] = await request.json()
        LOGGER.trace("DomikaAPIEntityListView: request_dict: %s", request_dict,)

        domains_list = cast(list[str], request_dict.get("domains"))
        entities = get(hass, domains_list, False)
        result = entities.to_dict()

        LOGGER.fine("DomikaAPIEntityListView data: %s", result)
        return self.json(result, HTTPStatus.OK)
