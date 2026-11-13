"""Removing an app session."""

from unittest.mock import AsyncMock, patch

from homeassistant.auth.permissions.events import SUBSCRIBE_ALLOWLIST

from custom_components.domika.sessions import router as sessions_router

from .conftest import add_session


async def test_removes_session_missing_from_subscribe_allowlist(hass, app_sessions):
    add_session(app_sessions, "s", "owner")
    SUBSCRIBE_ALLOWLIST.discard("domika_s")

    with patch.object(sessions_router, "_remove_push_session", AsyncMock()):
        await sessions_router._remove_app_session(hass, "s")

    assert app_sessions.get_app_session("s") is None
