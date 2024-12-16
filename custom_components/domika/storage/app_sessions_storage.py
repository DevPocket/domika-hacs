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
    DEVICE_INACTIVITY_TIME_THRESHOLD,
    DEVICE_INACTIVITY_CHECK_INTERVAL,
    APP_SESSIONS_STORAGE_DEFAULT_WRITE_DELAY
)
from ..utils import ReadWriteLock
from ..domika_logger import LOGGER

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
        LOGGER.debug("AppSessionsStorage Migrating users_data")
        if old_major_version > STORAGE_VERSION_APP_SESSIONS:
            raise ValueError("AppSessionsStorage can't migrate to future version")
        # Not implemented yet.
        if old_major_version == 1:
            pass
        # If we need migration — just clear all data.
        return {}


class AppSessionsStorage:
    def __init__(self):
        LOGGER.fine("AppSessionsStorage init started")
        self._store = None
        self._data: dict[str, Any] = {}
        self._push_subscriptions: dict[str, Any] = {}
        self._all_subscriptions: dict[str, Any] = {}
        self.rw_lock = ReadWriteLock()  # Read-write lock

    async def load_data(self, hass):
        LOGGER.fine("AppSessionsStorage load_data started")
        self.rw_lock.acquire_write()
        try:
            self._store = AppSessionsStore(
                hass, STORAGE_VERSION_APP_SESSIONS, STORAGE_KEY_APP_SESSIONS
            )

            if data := await self._store.async_load():
                self._data = data
                self._update_subscriptions_caches()
            LOGGER.finer("AppSessionsStorage loaded data from app sessions store: %s", self._data)
        finally:
            self.rw_lock.release_write()

    async def delete_storage(self):
        LOGGER.fine("AppSessionsStorage delete_storage started")
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

    def _save_app_sessions_data(self, delay=APP_SESSIONS_STORAGE_DEFAULT_WRITE_DELAY):
        def provide_data() -> dict:
            self.rw_lock.acquire_write()
            try:
                # TODO: Do we need this here? How do we protect from saving data while other thread is changing it?
                data_copy = copy.deepcopy(self._data)
                LOGGER.finest("AppSessionsStorage _save_app_sessions_data provided data: %s", data_copy)
                return copy.deepcopy(self._data)
            finally:
                self.rw_lock.release_write()

        LOGGER.finest("AppSessionsStorage _save_app_sessions_data started, delay: %s", delay)
        if self._store:
            self._store.async_delay_save(provide_data, delay)

    def push_subscriptions(self) -> dict:
        LOGGER.finest("AppSessionsStorage push_subscriptions returned: %s", self._push_subscriptions)
        return self._push_subscriptions

    def _get_subscription_cache(
            self,
            require_need_push: bool
    ) -> dict:
        """
        Returns
        {
            'entity_id1': {
                'app_session_id1': {
                    'push_session_id': '123',
                    'attributes': {'att1', 'att2'}
                },
                ……
            }
            ……
        }
        """
        LOGGER.finest("AppSessionsStorage _get_subscription_cache started, data: %s", self._data)
        res = {}

        for app_session_id, session_data in self._data.items():
            # Get the push_session_id; skip if it's None or empty
            push_session_id = session_data.get("push_session_id")
            if not push_session_id:
                continue

            # Process subscriptions
            subscriptions = session_data.get("subscriptions", [])
            for sub in subscriptions:
                if require_need_push and sub.get("need_push") != 1:
                    continue

                entity_id = sub.get("entity_id")
                attribute = sub.get("attribute")

                # Ensure entity_id exists in new_data
                if entity_id not in res:
                    res[entity_id] = {}

                # Ensure app_session_id exists under the entity_id in new_data
                if app_session_id not in res[entity_id]:
                    res[entity_id][app_session_id] = {
                        "push_session_id": push_session_id,
                        "attributes": set()
                    }

                # Add the attribute to the list
                res[entity_id][app_session_id]["attributes"].add(attribute)

        LOGGER.finest("AppSessionsStorage _get_subscription_cache, res: %s", res)
        return res

    def _update_subscriptions_caches(self):
        """
        Updates push_subscriptions and all_subscriptions
        The most frequent storage interaction is caused by new events,
        so we want to have a cache for those requests

        """
        self._push_subscriptions = self._get_subscription_cache(require_need_push=True)
        self._all_subscriptions = self._get_subscription_cache(require_need_push=False)

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
                LOGGER.finer(
                    'AppSessionsStorage: push session "%s" for app_session_id "%s" successfully removed',
                    data.get('push_session_id'),
                    app_session_id
                )
                data['push_session_id'] = None
            self._update_subscriptions_caches()
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
            self._update_subscriptions_caches()
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
            self._update_subscriptions_caches()
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
                LOGGER.verbose("AppSessionsStorage.app_session_resubscribe_push: "
                               "Can't update subscriptions for app_session_id: %s data: %s",
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
            self._update_subscriptions_caches()
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
            LOGGER.debug("AppSessionsStorage.app_session_resubscribe: Received empty or None subscriptions.")
            return

        self.rw_lock.acquire_write()
        try:
            data = self._data.get(app_session_id)
            if not data:
                LOGGER.debug("AppSessionsStorage.app_session_resubscribe: "
                             "No record found for app_session_id: %s",
                             app_session_id
                             )
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
            self._update_subscriptions_caches()
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
        Lock is not required as we are not accessing data directly, and cache is immutable.
        """

        return [
            app_session_id
            for app_session_id, session_data in self._all_subscriptions.get(entity_id, {}).items()
            if session_data.get('attributes', set()) & set(attributes)
        ]

    def delete_inactive(self, threshold):
        LOGGER.trace("AppSessionsStorage.delete_inactive started")
        self.rw_lock.acquire_write()
        try:
            for app_session_id, data in self._data.items():
                last_update_int = data.get('last_update')

                if last_update_int is None:
                    # No last_update timestamp, updating it
                    self._update_last_update(app_session_id)
                    LOGGER.finer("AppSessionsStorage.delete_inactive: no last_update timestamp for app_session_id: %s",
                                 app_session_id)
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
                    LOGGER.trace("AppSessionsStorage.delete_inactive: removed app_session_id: %s",
                                 app_session_id)
            self._update_subscriptions_caches()
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
                    LOGGER.error("Inactive sessions cleaner error")
                await asyncio.sleep(DEVICE_INACTIVITY_CHECK_INTERVAL.total_seconds())
        except asyncio.CancelledError as e:
            LOGGER.debug("Inactive sessions cleaner stopped. %s", e)
            raise
