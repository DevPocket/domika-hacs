"""Integration services api."""

import asyncio
from http import HTTPStatus

from aiohttp import web

from homeassistant.components.api import APIDomainServicesView
from homeassistant.core import async_get_hass
from homeassistant.helpers.json import json_bytes

from ..const import DOMAIN, LOGGER
from . import service as api_service
from ..push_data.pushdatastorage import PUSHDATA_STORAGE


class DomikaAPIDomainServicesView(APIDomainServicesView):
    """View to handle Status requests."""

    url = "/domika/services/{domain}/{service}"
    name = "domika:domain-services"

    async def post(
        self,
        request: web.Request,
        domain: str,
        service: str,
    ) -> web.Response:
        """Retrieve if API is running."""
        # Check that integration still loaded.
        hass = async_get_hass()
        if not hass.data.get(DOMAIN):
            return self.json_message("Route not found.", HTTPStatus.NOT_FOUND)

        # Perform control over entities via given request.
        response = await super().post(request, domain, service)

        app_session_id = request.headers.get("X-App-Session-Id")
        if not app_session_id:
            return self.json_message(
                "Missing  X-App-Session-Id.",
                HTTPStatus.UNAUTHORIZED,
            )

        delay = float(request.headers.get("X-Delay", 0.5))

        LOGGER.debug(
            "DomikaAPIDomainServicesView, domain: %s, service: %s, app_session_id: %s, "
            "delay: %s",
            domain,
            service,
            app_session_id,
            delay,
        )

        await asyncio.sleep(delay)

        PUSHDATA_STORAGE.remove_by_app_session_id(app_session_id=app_session_id)

        result = await api_service.get(app_session_id)

        LOGGER.debug("DomikaAPIDomainServicesView data: %s", {"entities": result})
        data = json_bytes({"entities": result})
        response.body = data
        return response
