"""Network properties sent to the app on update_app_session."""

import sys
import types
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.domika.sessions import router as sessions_router


class CloudNotAvailable(Exception):
    pass


@pytest.fixture
def hass() -> Mock:
    hass = Mock()
    hass.config.location_name = "Home"
    hass.config.external_url = None
    hass.config.internal_url = "http://ha.local:8123"
    hass.config.components = {"cloud"}
    hass.http.server_port = 8123
    return hass


def _cloud_module(remote_ui_url: Mock) -> types.ModuleType:
    # Stands in for homeassistant.components.cloud, whose import needs cloud's own requirements.
    module = types.ModuleType("homeassistant.components.cloud")
    module.CloudNotAvailable = CloudNotAvailable
    module.async_remote_ui_url = remote_ui_url
    return module


async def _properties(hass, remote_ui_url: Mock) -> dict:
    with (
        patch.dict(sys.modules, {"homeassistant.components.cloud": _cloud_module(remote_ui_url)}),
        patch.object(sessions_router, "is_hassio", return_value=False),
        patch.object(sessions_router.network, "async_get_announce_addresses", AsyncMock(return_value=["10.0.0.2"])),
    ):
        return await sessions_router._get_hass_network_properties(hass)


async def test_includes_cloud_instance_url(hass):
    remote_ui_url = Mock(return_value="https://abc.ui.nabu.casa")

    properties = await _properties(hass, remote_ui_url)

    remote_ui_url.assert_called_once_with(hass)
    assert properties == {
        "instance_name": "Home",
        "local_ip_port": "http://10.0.0.2:8123",
        "internal_url": "http://ha.local:8123",
        "cloud_url": "https://abc.ui.nabu.casa",
    }


async def test_omits_cloud_url_when_remote_ui_is_unavailable(hass):
    properties = await _properties(hass, Mock(side_effect=CloudNotAvailable))

    assert "cloud_url" not in properties


async def test_does_not_touch_cloud_when_it_is_not_loaded(hass):
    hass.config.components = set()
    remote_ui_url = Mock()

    properties = await _properties(hass, remote_ui_url)

    remote_ui_url.assert_not_called()
    assert "cloud_url" not in properties
