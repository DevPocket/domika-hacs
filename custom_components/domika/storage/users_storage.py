"""Users storage module."""

from __future__ import annotations

import copy
from contextlib import suppress
from typing import Any

from homeassistant.helpers.storage import Store
from ..const import DOMAIN, USERS_STORAGE_DEFAULT_WRITE_DELAY
from ..domika_logger import LOGGER
from ..utils import ReadWriteLock
from .models import UsersData

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
        LOGGER.debug("UsersStorage Migrating users_data")
        if old_major_version > STORAGE_VERSION_USERS:
            raise ValueError("Can't migrate to future version")
        # Not implemented yet.
        if old_major_version == 1:
            pass
        return old_data  # type: ignore[return-value]


class UsersStorage:
    def __init__(self):
        LOGGER.fine("UsersStorage init started")
        self._store = None
        self._data: dict[str, Any] = {}
        self.rw_lock = ReadWriteLock()  # Read-write lock

    async def load_data(self, hass):
        LOGGER.fine("UsersStorage load_data started")
        self.rw_lock.acquire_write()
        try:
            self._store = UsersStore(
                hass, STORAGE_VERSION_USERS, STORAGE_KEY_USERS
            )
            if users_data := await self._store.async_load():
                self._data = users_data
            LOGGER.finer("UsersStorage loaded data from app sessions store: %s", self._data)
        finally:
            self.rw_lock.release_write()

    async def delete_storage(self):
        LOGGER.fine("UsersStorage delete_storage started")
        self.rw_lock.acquire_write()
        try:
            if self._store:
                await self._store.async_remove()
        finally:
            self._store = None
            self._data = {}
            self._push_subscriptions = {}
            self._all_subscriptions = {}
            self.rw_lock.release_write()

    def _save_users_data(self, delay=USERS_STORAGE_DEFAULT_WRITE_DELAY):
        def provide_data() -> dict:
            self.rw_lock.acquire_write()
            try:
                data_copy = copy.deepcopy(self._data)
                LOGGER.finest("UsersStorage _save_app_sessions_data provided data: %s", data_copy)
                return data_copy
            finally:
                self.rw_lock.release_write()

        LOGGER.finest("UsersStorage _save_app_sessions_data started, delay: %s", delay)
        if self._store:
            self._store.async_delay_save(provide_data, delay)

    def update_users_data(
            self,
            user_id: str,
            key: str,
            value: str,
            value_hash: str
    ):
        LOGGER.finer("UsersStorage.update_users_data, user_id: %s, key: %s, value: %s, value_hash: %s",
                     user_id,
                     key,
                     value,
                     value_hash
                     )
        self.rw_lock.acquire_write()
        try:
            if not self._data.get(user_id):
                self._data[user_id] = {}
            self._data[user_id][key] = {'value': value, 'value_hash': value_hash}
        finally:
            self.rw_lock.release_write()
            self._save_users_data()

    def get_users_data(
            self,
            user_id: str,
            key: str
    ) -> UsersData | None:
        res: UsersData | None = None
        LOGGER.finer("UsersStorage.get_users_data, user_id: %s, key: %s", user_id, key)

        self.rw_lock.acquire_read()
        try:
            with suppress(KeyError):
                res = UsersData(self._data[user_id][key]['value'], self._data[user_id][key]['value_hash'])
        finally:
            self.rw_lock.release_read()

        LOGGER.finer("UsersStorage.get_users_data, res: %s", res)
        return res
