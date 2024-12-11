"""Storage module."""

from __future__ import annotations

import threading
from datetime import datetime

import sqlalchemy
from homeassistant.helpers.storage import Store
from sqlalchemy.exc import SQLAlchemyError

from ..const import DOMAIN, LOGGER
from ..domika_ha_framework.database import core as database_core
from .models import *

STORAGE_VERSION_USERS = 1
STORAGE_VERSION_APP_SESSIONS = 1
STORAGE_KEY_USERS = f"{DOMAIN}/users_storage.json"
STORAGE_KEY_APP_SESSIONS = f"{DOMAIN}/app_sessions_storage.json"

USERS_LOCK = threading.Lock()
APP_SESSIONS_LOCK = threading.Lock()


# {
#     USER_ID: {KEY: {"value": V, "value_hash": VH}},
#     USER_ID1: {KEY1: {"value": V1, "value_hash": VH1}}
#  }
class UsersStore(Store[dict[str, Any]]):
    async def migrate_from_db(self) -> dict[str, Any] | None:
        LOGGER.debug("---> Migrating users_data from DB")
        try:
            async with database_core.get_session() as session:
                stmt = sqlalchemy.select(KeyValue)
                db_res = (await session.scalars(stmt)).all()
        except SQLAlchemyError as e:
            LOGGER.error("---> Can't migrate from DB: DB error")

        res = {}
        for key_value in db_res:
            LOGGER.debug("---> found in DB: %s, %s", key_value.user_id, key_value.key)
            if not res.get(key_value.user_id):
                res[key_value.user_id] = {}
            res[key_value.user_id][key_value.key] = {'value': key_value.value, 'value_hash': key_value.hash}
        return res

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


# {
#     APP_SESSION_ID: {
#       "user_id": user_id,
#       "push_session_id": push_session_id,
#       "last_update": timestamp,
#       "push_token_hash": push_token_hash,
#       "subscriptions":
#           [
#               {"entity_id": id, "attribute": att, "need_push": 1},
#               {"entity_id": id1, "attribute": att1, "need_push": 0},
#               ………
#           ]
#     },
#     …………
#  }
class AppSessionsStore(Store[dict[str, Any]]):
    async def _async_migrate_func(
            self,
            old_major_version: int,
            old_minor_version: int,
            old_data: dict[str, Any]
    ) -> Store[dict[str, Any]]:
        """Migrate to the new version."""
        LOGGER.debug("---> Migrating users_data")
        if old_major_version > STORAGE_VERSION_APP_SESSIONS:
            raise ValueError("Can't migrate to future version")
        # Not implemented yet.
        if old_major_version == 1:
            pass
        return old_data  # type: ignore[return-value]


class AppSession:
    id: str
    user_id: str
    push_session_id: str
    last_update: datetime
    push_token_hash: str

    def __init__(self, id, user_id, push_session_id, last_update, push_token_hash):
        self.id = id
        self.user_id = user_id
        self.push_session_id = push_session_id
        self.last_update = last_update
        self.push_token_hash = push_token_hash

    @staticmethod
    def init_from_dict(app_session_id: str, d: dict):
        return AppSession(
            id=app_session_id,
            user_id=d.get("user_id"),
            push_session_id=d.get("push_session_id"),
            last_update=d.get("last_update"),
            push_token_hash=d.get("push_token_hash")
        )


class Storage:
    def __init__(self):
        self._users_store = None
        self._users_data: dict[str, Any] | None = {}
        self._app_sessions_store = None
        self._app_sessions_data: dict[str, Any] | None = {}

    async def load_data(self, hass):
        self._users_store = UsersStore(
            hass, STORAGE_VERSION_USERS, STORAGE_KEY_USERS
        )
        if (users_data := await self._users_store.async_load()) is None:
            LOGGER.debug("---> Can't load data from users_storage")
            self._users_data = await self._users_store.migrate_from_db()
            await self._save_users_data()
        else:
            LOGGER.debug("---> Loaded data from users_storage: %s", users_data)
            self._users_data = users_data

        self._app_sessions_store = AppSessionsStore(
            hass, STORAGE_VERSION_APP_SESSIONS, STORAGE_KEY_APP_SESSIONS
        )
        if (app_sessions_data := await self._app_sessions_store.async_load()) is None:
            LOGGER.debug("---> Can't load data from app_sessions storage")
            self._app_sessions_data = {}
        else:
            LOGGER.debug("---> Loaded data from app_sessions storage: %s", app_sessions_data)
            self._app_sessions_data = app_sessions_data

    async def _save_users_data(self):
        await self._users_store.async_save(self._users_data)
        LOGGER.debug("---> Saved users_data to users storage")

    async def _save_app_sessions_data(self):
        await self._app_sessions_store.async_save(self._app_sessions_data)
        LOGGER.debug("---> Saved users_data to app_sessions storage")

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
        with USERS_LOCK:
            if not self._users_data.get(user_id):
                return None
            if not self._users_data[user_id].get(key):
                return None
            LOGGER.debug("---> Got users_data for user: %s, key: %s", user_id, key)
            return self._users_data[user_id][key]['value'], self._users_data[user_id][key]['value_hash']

    async def update_app_session(
            self,
            app_session: AppSession
    ):
        with APP_SESSIONS_LOCK:
            if not self._app_sessions_data.get(app_session.id):
                self._app_sessions_data[app_session.id] = {}
            self._app_sessions_data[app_session.id]['user_id'] = app_session.user_id
            self._app_sessions_data[app_session.id]['push_session_id'] = app_session.push_session_id
            self._app_sessions_data[app_session.id]['last_update'] = str(app_session.last_update)
            self._app_sessions_data[app_session.id]['push_token_hash'] = app_session.push_token_hash
            LOGGER.debug("---> Updated app_sessions_data for app_session: %s", app_session.id)
        await self._save_app_sessions_data()

    def get_app_session(
            self,
            app_session_id: str
    ) -> AppSession | None:
        with APP_SESSIONS_LOCK:
            if not self._app_sessions_data.get(app_session_id):
                return None
            return AppSession.init_from_dict(app_session_id, self._app_sessions_data.get(app_session_id))




STORAGE: Storage | None = Storage()


async def init_storage(hass):
    await STORAGE.load_data(hass)
