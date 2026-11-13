"""Shared fixtures."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from custom_components.domika.const import DOMAIN
from custom_components.domika.push_data_storage.pushdatastorage import PUSHDATA_STORAGE
from custom_components.domika.storage import APP_SESSIONS_STORAGE


@pytest.fixture
def app_sessions():
    """The global app sessions storage, emptied and with saving disabled."""
    APP_SESSIONS_STORAGE._data = {}
    APP_SESSIONS_STORAGE._update_subscriptions_caches()
    with patch.object(APP_SESSIONS_STORAGE, "_save_app_sessions_data"):
        yield APP_SESSIONS_STORAGE
    APP_SESSIONS_STORAGE._data = {}
    APP_SESSIONS_STORAGE._update_subscriptions_caches()


@pytest.fixture
def push_data():
    """The global push data storage, emptied."""
    PUSHDATA_STORAGE.storage = {}
    yield PUSHDATA_STORAGE
    PUSHDATA_STORAGE.storage = {}


def add_session(
        storage,
        app_session_id: str,
        user_id: str,
        *,
        push_token_hash: str = "",
        push_session_id: str | None = None,
        subscriptions: list[dict] | None = None,
        last_update: int | None = None,
) -> None:
    storage._data[app_session_id] = {
        "user_id": user_id,
        "push_session_id": push_session_id,
        "last_update": last_update if last_update is not None else int(datetime.now().timestamp()),
        "push_token_hash": push_token_hash,
        "subscriptions": subscriptions or [],
    }
    storage._update_subscriptions_caches()


@pytest.fixture
def hass():
    """A minimal hass stand-in with a loaded Domika entry whose tasks are recorded, not run."""
    entry = Mock()
    entry.async_create_task.side_effect = lambda _hass, coro, _name: coro.close()
    hass = Mock()
    hass.data = {DOMAIN: {"entry": entry}}
    hass.states.get.return_value = None
    return hass


def make_connection(user_id: str) -> MagicMock:
    connection = MagicMock()
    connection.user.id = user_id
    return connection
