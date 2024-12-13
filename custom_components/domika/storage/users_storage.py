"""Users storage module."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.storage import Store
from ..const import DOMAIN, LOGGER, USERS_STORAGE_DEFAULT_WRITE_DELAY

from ..utils import ReadWriteLock

STORAGE_VERSION_USERS = 1
STORAGE_KEY_USERS = f"{DOMAIN}/users_storage.json"


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
    ) -> dict[str, Any]:
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
        self._store = None
        self._data: dict[str, Any] = {}
        self.rw_lock = ReadWriteLock()  # Read-write lock

    async def load_data(self, hass):
        self.rw_lock.acquire_write()
        try:
            self._store = UsersStore(
                hass, STORAGE_VERSION_USERS, STORAGE_KEY_USERS
            )
            if users_data := await self._store.async_load():
                self._data = users_data
            LOGGER.debug("Loaded data from users store: %s", self._data)
        finally:
            self.rw_lock.release_write()

    async def _save_users_data(self, delay=USERS_STORAGE_DEFAULT_WRITE_DELAY):
        if self._store:
            if not delay:
                await self._store.async_save(self._data)
            else:
                await self._store.async_delay_save(self._data, delay)

    async def update_users_data(
            self,
            user_id: str,
            key: str,
            value: str,
            value_hash: str
    ):
        self.rw_lock.acquire_write()
        try:
            if not self._data.get(user_id):
                self._data[user_id] = {}
            self._data[user_id][key] = {'value': value, 'value_hash': value_hash}
            LOGGER.debug("---> Updated users_data for user: %s, key: %s", user_id, key)
            await self._save_users_data()
        finally:
            self.rw_lock.release_write()

    def get_users_data(
            self,
            user_id: str,
            key: str
    ) -> tuple[str, str] | None:
        self.rw_lock.acquire_read()
        try:
            if not self._data.get(user_id):
                return None
            if not self._data[user_id].get(key):
                return None
            LOGGER.debug("---> Got users_data for user: %s, key: %s", user_id, key)
            return self._data[user_id][key]['value'], self._data[user_id][key]['value_hash']
        finally:
            self.rw_lock.release_read()
