"""Storage module."""

from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import datetime
from typing import Any, List

from .models import AppSession, Subscription
from homeassistant.helpers.storage import Store
from ..const import DOMAIN, LOGGER, DEVICE_INACTIVITY_TIME_THRESHOLD, DEVICE_INACTIVITY_CHECK_INTERVAL

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


class Storage:
    def __init__(self):
        self._users_store = None
        self._users_data: dict[str, Any] = {}
        self._app_sessions_store = None
        self._app_sessions_data: dict[str, Any] = {}

    async def load_data(self, hass):
        await self.load_data_users(hass)
        await self.load_data_app_sessions(hass)

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

    async def load_data_app_sessions(self, hass):
        with APP_SESSIONS_LOCK:
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

    async def _save_app_sessions_data(self):
        await self._app_sessions_store.async_save(self._app_sessions_data)

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

    def get_all_app_sessions_data(self) -> dict:
        return self._app_sessions_data

    # Returns AppSession object, or None if not found
    def get_app_session(
            self,
            app_session_id: str
    ) -> AppSession | None:
        if not self._app_sessions_data.get(app_session_id):
            return None
        return AppSession.init_from_dict(app_session_id, self._app_sessions_data.get(app_session_id))

    # Returns AppSession object, or None if not found
    async def update_app_session_last_update(
            self,
            app_session_id: str
    ):
        with APP_SESSIONS_LOCK:
            if self._app_sessions_data.get(app_session_id):
                self._app_sessions_data[app_session_id]['last_update'] = int(datetime.now().timestamp())
                await self._save_app_sessions_data()

    async def update_push_token(
            self,
            app_session_id: str,
            push_session_id: str,
            push_token_hash: str
    ):
        with APP_SESSIONS_LOCK:
            if data := self._app_sessions_data.get(app_session_id):
                data['push_session_id'] = push_session_id
                data['push_token_hash'] = push_token_hash
                await self._save_app_sessions_data()

    async def remove_push_session(
            self,
            app_session_id: str,
    ):
        with APP_SESSIONS_LOCK:
            if data := self._app_sessions_data.get(app_session_id):
                data['push_session_id'] = ''
                await self._save_app_sessions_data()

    # Returns AppSession object, or None if not found
    async def remove_app_session(
            self,
            app_session_id: str
    ):
        with APP_SESSIONS_LOCK:
            if self._app_sessions_data.get(app_session_id):
                self._app_sessions_data.pop(app_session_id)
                await self._save_app_sessions_data()

    # Remove all app_session records with given push_token
    # except one given app_session_id
    async def remove_app_sessions_with_push_token(self, push_token: str, except_app_session_id: str):
        for app_session_id, data in self._app_sessions_data.items():
            if app_session_id == except_app_session_id:
                continue
            if data.get("push_token_hash") == push_token:
                await self.remove_app_session(app_session_id)

    # Create AppSession object
    async def create_app_session(
            self,
            user_id: str,
            push_token_hash: str
    ) -> str:
        with APP_SESSIONS_LOCK:
            new_id = str(uuid.uuid4())
            self._app_sessions_data[new_id] = {}
            self._app_sessions_data[new_id]['user_id'] = user_id
            self._app_sessions_data[new_id]['push_session_id'] = None
            self._app_sessions_data[new_id]['last_update'] = int(datetime.now().timestamp())
            self._app_sessions_data[new_id]['push_token_hash'] = push_token_hash
            await self._save_app_sessions_data()
            return new_id

    # Updates all subscriptions for the given app_session_id.
    # Sets need_push=1 for all given subscriptions, and 0 for all others.
    async def app_session_resubscribe_push(
            self,
            app_session_id: str,
            subscriptions: dict[str, set[str]]
    ):
        with APP_SESSIONS_LOCK:
            data = self._app_sessions_data.get(app_session_id)

            if not data or not data.get("subscriptions"):
                LOGGER.debug(
                    "app_session_resubscribe_push: Can't update subscriptions for app_session_id: %s data: %s",
                    app_session_id, self._app_sessions_data
                )
                return

            current_subs = data["subscriptions"]

            # Update subscriptions with appropriate need_push values
            for sub in current_subs:
                entity_id = sub.get("entity_id")
                attribute = sub.get("attribute")

                if entity_id and attribute:
                    sub["need_push"] = "1" if entity_id in subscriptions and attribute in subscriptions[
                        entity_id] else "0"

        # Save the updated data
        await self._save_app_sessions_data()

    # Removes all subscriptions for the given app_session_id and creates new ones.
    async def app_session_resubscribe(
            self,
            app_session_id: str,
            subscriptions: dict[str, dict[str, int]]
    ):
        if not subscriptions:
            LOGGER.error("app_session_resubscribe: Received empty or None subscriptions.")
            return

        with APP_SESSIONS_LOCK:
            data = self._app_sessions_data.get(app_session_id)
            if not data:
                LOGGER.error("app_session_resubscribe: No record found for app_session_id: %s", app_session_id)
                return

            # Create new subscriptions
            new_subscriptions = [
                {"entity_id": entity_id, "attribute": att, "need_push": str(need_push)}
                for entity_id, atts in subscriptions.items()
                if atts
                for att, need_push in atts.items()
            ]

            # Update the data and save
            data["subscriptions"] = new_subscriptions
            await self._save_app_sessions_data()

    def get_app_session_ids_with_hash(self, push_token_hash: str) -> list[str]:
        return [
            app_session_id
            for app_session_id, data in self._app_sessions_data.items()
            if data.get('push_token_hash') == push_token_hash
        ]

    def get_app_session_ids_by_user_id(self, user_id: str) -> list[str]:
        return [
            app_session_id
            for app_session_id, data in self._app_sessions_data.items()
            if data.get('user_id') == user_id
        ]

    def get_app_session_ids_with_push_session(self) -> list[AppSession]:
        return [
            self.get_app_session(app_session_id)
            for app_session_id, data in self._app_sessions_data.items()
            if data.get('push_sessionId')
        ]

    def get_app_session_subscriptions(
            self,
            app_session_id: str,
            *,
            need_push: bool | None = True,
            entity_id: str | None = None,
    ) -> list[Subscription]:
        data: dict = self._app_sessions_data.get(app_session_id)
        if not data or not data.get("subscriptions"):
            return []

        return [
            Subscription(sub.get('entity_id'), sub.get('attribute'), bool(sub.get('need_push')))
            for sub in data.get("subscriptions", [])
            if (entity_id is None or sub.get('entity_id') == entity_id)
                and (need_push is None or bool(sub.get('need_push')) == need_push)
        ]

    def get_app_sessions_for_event(self, entity_id: str, attributes: list[str]) -> list[str]:
        """
        Get the list of app_session_ids subscribed to any of the given attributes
        for the specified entity_id.
        """
        subscribed_app_sessions = []

        for app_session_id, session_data in self._app_sessions_data.items():
            subscriptions = session_data.get("subscriptions", [])
            for subscription in subscriptions:
                # Check if the subscription matches the entity_id and any attribute
                if subscription.get("entity_id") == entity_id and subscription.get("attribute") in attributes:
                    subscribed_app_sessions.append(app_session_id)
                    break  # Break out as we only need to add the app_session_id once
        return subscribed_app_sessions

    async def delete_inactive(self, threshold):
        for app_session, data in self._app_sessions_data.items():
            last_update_int = data.get('last_update')

            if last_update_int is None:
                # No last_update timestamp, updating it
                await self.update_app_session_last_update(app_session)
                continue

            try:
                last_update = datetime.fromtimestamp(last_update_int)
            except (ValueError, OSError) as e:
                LOGGER.debug("Invalid last_update format for app_session %s: %s", app_session, last_update_int)
                await self.update_app_session_last_update(app_session)
                continue

            if datetime.now() - last_update > threshold:
                await self.remove_app_session(app_session)

    async def inactive_device_cleaner(self) -> None:
        """
        Start new inactive sessions cleaner loop.
        Periodically removes outdated devices.
        """
        LOGGER.debug("Inactive sessions cleaner started")
        try:
            while True:
                try:
                    await self.delete_inactive(
                        DEVICE_INACTIVITY_TIME_THRESHOLD,
                    )
                except Exception:  # noqa: BLE001
                    LOGGER.exception("Inactive sessions cleaner error")
                await asyncio.sleep(DEVICE_INACTIVITY_CHECK_INTERVAL.total_seconds())
        except asyncio.CancelledError as e:
            LOGGER.debug("Inactive sessions cleaner stopped. %s", e)
            raise


STORAGE: Storage | None = Storage()


async def init_storage(hass):
    await STORAGE.load_data(hass)
