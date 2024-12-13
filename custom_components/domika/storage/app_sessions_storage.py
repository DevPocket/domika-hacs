"""App sessions storage module."""

from __future__ import annotations

import asyncio
import copy
import uuid
from datetime import datetime
from typing import Any

from .models import AppSession, Subscription, Sessions
from homeassistant.helpers.storage import Store
from ..const import (
    DOMAIN,
    LOGGER,
    DEVICE_INACTIVITY_TIME_THRESHOLD,
    DEVICE_INACTIVITY_CHECK_INTERVAL,
    APP_SESSIONS_STORAGE_DEFAULT_WRITE_DELAY
)
from ..utils import ReadWriteLock

STORAGE_VERSION_APP_SESSIONS = 1
STORAGE_KEY_APP_SESSIONS = f"{DOMAIN}/app_sessions_storage.json"


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
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        LOGGER.debug("---> Migrating users_data")
        if old_major_version > STORAGE_VERSION_APP_SESSIONS:
            raise ValueError("Can't migrate to future version")
        # Not implemented yet.
        if old_major_version == 1:
            pass
        # If we need migration — just clear all data.
        return {}


class AppSessionsStorage:
    def __init__(self):
        self._store = None
        self._data: dict[str, Any] = {}
        self.rw_lock = ReadWriteLock()  # Read-write lock

    async def load_data(self, hass):
        self.rw_lock.acquire_write()
        try:
            self._store = AppSessionsStore(
                hass, STORAGE_VERSION_APP_SESSIONS, STORAGE_KEY_APP_SESSIONS
            )

            if data := await self._store.async_load():
                self._data = data
            LOGGER.debug("Loaded data from app sessions store: %s", self._data)
        finally:
            self.rw_lock.release_write()

    def _save_app_sessions_data(self, delay=APP_SESSIONS_STORAGE_DEFAULT_WRITE_DELAY):
        def provide_data() -> dict:
            self.rw_lock.acquire_write()
            try:
                # TODO: Do we need this here? How do we protect from saving data while other thread is changing it?
                return copy.deepcopy(self._data)
            finally:
                self.rw_lock.release_write()

        if self._store:
            self._store.async_delay_save(provide_data, delay)

    def get_data_copy(self) -> dict:
        self.rw_lock.acquire_read()
        try:
            return copy.deepcopy(self._data)
        finally:
            self.rw_lock.release_read()

    # Returns AppSession object, or None if not found
    def get_app_session(
            self,
            app_session_id: str
    ) -> AppSession | None:
        self.rw_lock.acquire_read()
        try:
            if not self._data.get(app_session_id):
                return None
            return AppSession.init_from_dict(app_session_id, self._data.get(app_session_id))
        finally:
            self.rw_lock.release_read()

    def _update_last_update(
            self,
            app_session_id: str
    ):
        if data := self._data.get(app_session_id):
            data['last_update'] = int(datetime.now().timestamp())

    # Returns AppSession object, or None if not found
    def update_last_update(
            self,
            app_session_id: str
    ):
        self.rw_lock.acquire_write()
        try:
            self._update_last_update(app_session_id)
        finally:
            self.rw_lock.release_write()
            self._save_app_sessions_data()

    def update_push_session(
            self,
            app_session_id: str,
            push_session_id: str,
            push_token_hash: str
    ):
        self.rw_lock.acquire_write()
        try:
            if data := self._data.get(app_session_id):
                data['push_session_id'] = push_session_id
                data['push_token_hash'] = push_token_hash
        finally:
            self.rw_lock.release_write()
            self._save_app_sessions_data()

    def remove_push_session(
            self,
            app_session_id: str,
    ):
        self.rw_lock.acquire_write()
        try:
            if data := self._data.get(app_session_id):
                data['push_session_id'] = None
                LOGGER.info(
                    'Push session for app session "%s" successfully removed',
                    app_session_id,
                )
        finally:
            self.rw_lock.release_write()
            self._save_app_sessions_data()

    def remove(
            self,
            app_session_id: str
    ):
        self.rw_lock.acquire_write()
        try:
            self._data.pop(app_session_id, None)
        finally:
            self.rw_lock.release_write()
            self._save_app_sessions_data()

    # Remove all app_session records with given push_token
    # except one given app_session_id
    def remove_all_with_push_token_hash(
            self,
            push_token_hash: str,
            except_app_session_id: str
    ):
        self.rw_lock.acquire_write()
        try:
            for app_session_id, data in self._data.items():
                if app_session_id != except_app_session_id and data.get("push_token_hash") == push_token_hash:
                    self._data.pop(app_session_id, None)
        finally:
            self.rw_lock.release_write()
            self._save_app_sessions_data()

    # Create AppSession object
    def create(
            self,
            user_id: str,
            push_token_hash: str
    ) -> str:
        self.rw_lock.acquire_write()
        try:
            new_id = str(uuid.uuid4())
            self._data[new_id] = {
                'user_id': user_id,
                'push_session_id': None,
                'last_update': int(datetime.now().timestamp()),
                'push_token_hash': push_token_hash,
            }
            return new_id
        finally:
            self.rw_lock.release_write()
            self._save_app_sessions_data()

    # Updates all subscriptions for the given app_session_id.
    # Sets need_push=1 for all given subscriptions, and 0 for all others.
    def resubscribe_push(
            self,
            app_session_id: str,
            subscriptions: dict[str, set[str]]
    ):
        self.rw_lock.acquire_write()
        try:
            data = self._data.get(app_session_id)

            if not data or not data.get("subscriptions"):
                LOGGER.debug(
                    "app_session_resubscribe_push: Can't update subscriptions for app_session_id: %s data: %s",
                    app_session_id, self._data
                )
                return

            current_subs = data["subscriptions"]

            # Update subscriptions with appropriate need_push values
            for sub in current_subs:
                entity_id = sub.get("entity_id")
                attribute = sub.get("attribute")

                if entity_id and attribute:
                    sub["need_push"] = 1 if entity_id in subscriptions and attribute in subscriptions[
                        entity_id] else 0
        finally:
            self.rw_lock.release_write()
            self._save_app_sessions_data()

    # Removes all subscriptions for the given app_session_id and creates new ones.
    def resubscribe(
            self,
            app_session_id: str,
            subscriptions: dict[str, dict[str, int]]
    ):
        if not subscriptions:
            LOGGER.error("app_session_resubscribe: Received empty or None subscriptions.")
            return

        self.rw_lock.acquire_write()
        try:
            data = self._data.get(app_session_id)
            if not data:
                LOGGER.error("app_session_resubscribe: No record found for app_session_id: %s", app_session_id)
                return

            # Create new subscriptions
            new_subscriptions = [
                {"entity_id": entity_id, "attribute": att, "need_push": need_push}
                for entity_id, atts in subscriptions.items()
                if atts
                for att, need_push in atts.items()
            ]

            # Update the data and save
            data["subscriptions"] = new_subscriptions
        finally:
            self.rw_lock.release_write()
            self._save_app_sessions_data()

    def get_app_session_ids_with_hash(self, push_token_hash: str) -> list[str]:
        self.rw_lock.acquire_read()
        try:
            return [
                app_session_id
                for app_session_id, data in self._data.items()
                if data.get('push_token_hash') == push_token_hash
            ]
        finally:
            self.rw_lock.release_read()

    def get_app_session_ids_by_user_id(self, user_id: str) -> list[str]:
        self.rw_lock.acquire_read()
        try:
            return [
                app_session_id
                for app_session_id, data in self._data.items()
                if data.get('user_id') == user_id
            ]
        finally:
            self.rw_lock.release_read()

    def get_app_sessions_with_push_session(self) -> list[Sessions]:
        self.rw_lock.acquire_read()
        try:
            return [
                Sessions(app_session_id, data.get('push_session_id'))
                for app_session_id, data in self._data.items()
                if data.get('push_session_id')
            ]
        finally:
            self.rw_lock.release_read()

    def get_subscriptions(
            self,
            app_session_id: str,
            *,
            need_push: bool | None = True,
            entity_id: str | None = None,
    ) -> list[Subscription]:
        self.rw_lock.acquire_read()
        try:
            data: dict = self._data.get(app_session_id)
            if not data or not data.get("subscriptions"):
                return []

            return [
                Subscription(app_session_id, sub.get('entity_id'), sub.get('attribute'), bool(sub.get('need_push')))
                for sub in data.get("subscriptions", [])
                if (not entity_id or sub.get('entity_id') == entity_id)
                   and (not need_push or bool(sub.get('need_push')) == need_push)
            ]
        finally:
            self.rw_lock.release_read()

    def get_app_sessions_for_event(self, entity_id: str, attributes: list[str]) -> list[str]:
        """
        Get the list of app_session_ids subscribed to any of the given attributes
        for the specified entity_id.
        """
        subscribed_app_sessions = []

        self.rw_lock.acquire_read()
        try:
            for app_session_id, session_data in self._data.items():
                subscriptions = session_data.get("subscriptions", [])
                for subscription in subscriptions:
                    # Check if the subscription matches the entity_id and any attribute
                    if subscription.get("entity_id") == entity_id and subscription.get("attribute") in attributes:
                        subscribed_app_sessions.append(app_session_id)
                        break  # Break out as we only need to add the app_session_id once
            return subscribed_app_sessions
        finally:
            self.rw_lock.release_read()

    def delete_inactive(self, threshold):
        self.rw_lock.acquire_write()
        try:
            for app_session_id, data in self._data.items():
                last_update_int = data.get('last_update')

                if last_update_int is None:
                    # No last_update timestamp, updating it
                    self._update_last_update(app_session_id)
                    continue

                try:
                    last_update = datetime.fromtimestamp(last_update_int)
                except (ValueError, OSError):
                    LOGGER.debug(
                        "Invalid last_update format for app_session_id %s: %s",
                        app_session_id,
                        last_update_int
                    )
                    self._update_last_update(app_session_id)
                    continue

                if datetime.now() - last_update > threshold:
                    self._data.pop(app_session_id, None)
        finally:
            self.rw_lock.release_write()
            self._save_app_sessions_data()

    async def inactive_device_cleaner(self) -> None:
        """
        Start new inactive sessions cleaner loop.
        Periodically removes outdated devices.
        """
        LOGGER.debug("Inactive sessions cleaner started")
        try:
            while True:
                try:
                    self.delete_inactive(
                        DEVICE_INACTIVITY_TIME_THRESHOLD,
                    )
                except Exception:  # noqa: BLE001
                    LOGGER.exception("Inactive sessions cleaner error")
                await asyncio.sleep(DEVICE_INACTIVITY_CHECK_INTERVAL.total_seconds())
        except asyncio.CancelledError as e:
            LOGGER.debug("Inactive sessions cleaner stopped. %s", e)
            raise
