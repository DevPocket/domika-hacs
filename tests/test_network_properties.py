"""Network properties sent to the app on update_app_session."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.helpers.network import NoURLAvailableError

from custom_components.domika.sessions import router as sessions_router


@pytest.fixture
def hass() -> Mock:
    hass = Mock()
    hass.config.location_name = "Home"
    hass.config.external_url = None
    hass.config.internal_url = "http://ha.local:8123"
    hass.http.server_port = 8123
    return hass


async def _properties(hass, get_url) -> dict:
    with (
        patch.object(sessions_router, "is_hassio", return_value=False),
        patch.object(sessions_router.network, "async_get_announce_addresses", AsyncMock(return_value=["10.0.0.2"])),
        patch.object(sessions_router, "get_url", get_url),
    ):
        return await sessions_router._get_hass_network_properties(hass)


async def test_includes_cloud_url_when_remote_ui_is_available(hass):
    get_url = Mock(return_value="https://abc.ui.nabu.casa")

    properties = await _properties(hass, get_url)

    get_url.assert_called_once_with(hass, require_cloud=True)
    assert properties == {
        "instance_name": "Home",
        "local_ip_port": "http://10.0.0.2:8123",
        "internal_url": "http://ha.local:8123",
        "cloud_url": "https://abc.ui.nabu.casa",
    }


async def test_omits_cloud_url_without_remote_ui(hass):
    properties = await _properties(hass, Mock(side_effect=NoURLAvailableError))

    assert "cloud_url" not in properties
    assert properties["internal_url"] == "http://ha.local:8123"
