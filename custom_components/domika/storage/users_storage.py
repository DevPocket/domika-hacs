"""Users storage module."""

from __future__ import annotations

import threading
from typing import Any

from homeassistant.helpers.storage import Store
from ..const import DOMAIN, LOGGER

STORAGE_VERSION_USERS = 1
STORAGE_KEY_USERS = f"{DOMAIN}/users_storage.json"

USERS_LOCK = threading.Lock()


# {
#     USER_ID: {KEY: {"value": V, "value_hash": VH}},
#     USER_ID1: {KEY1: {"value": V1, "value_hash": VH1}}
#  }
class UsersStore(Store[dict[str, Any]]):
    async def _async_migrate_func(
            self,
            old_major_version: int,
            old_minor_version: int,
            old_data: dict[str, Any]
    ) -> Store[dict[str, Any]]:
        """Migrate to the new version."""
        LOGGER.debug("---> Migrating users_data")
        if old_major_version > STORAGE_VERSION_USERS:
            raise ValueError("Can't migrate to future version")
        # Not implemented yet.
        if old_major_version == 1:
            pass
        return old_data  # type: ignore[return-value]


class UsersStorage:
    def __init__(self):
        self._users_store = None
        self._users_data: dict[str, Any] = {}

    async def load_data(self, hass):
        await self.load_data_users(hass)

    async def load_data_users(self, hass):
        with USERS_LOCK:
            self._users_store = UsersStore(
                hass, STORAGE_VERSION_USERS, STORAGE_KEY_USERS
            )
            if (users_data := await self._users_store.async_load()) is None:
                LOGGER.debug("---> Can't load data from users_storage")
            else:
                LOGGER.debug("---> Loaded data from users_storage: %s", users_data)
                self._users_data = users_data

    async def _save_users_data(self):
        await self._users_store.async_save(self._users_data)

    async def update_users_data(
            self,
            user_id: str,
            key: str,
            value: str,
            value_hash: str
    ):
        with USERS_LOCK:
            if not self._users_data.get(user_id):
                self._users_data[user_id] = {}
            self._users_data[user_id][key] = {'value': value, 'value_hash': value_hash}
            LOGGER.debug("---> Updated users_data for user: %s, key: %s", user_id, key)
            await self._save_users_data()

    def get_users_data(
            self,
            user_id: str,
            key: str
    ) -> tuple[str, str] | None:
        if not self._users_data.get(user_id):
            return None
        if not self._users_data[user_id].get(key):
            return None
        LOGGER.debug("---> Got users_data for user: %s, key: %s", user_id, key)
        return self._users_data[user_id][key]['value'], self._users_data[user_id][key]['value_hash']
