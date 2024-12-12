"""Pushdata module."""
from .models import PushData
import threading
from typing import List


class PushDataStorage:
    def __init__(self):
        """ Use a dictionary to index by (app_session_id, entity_id, attribute) for fast lookups """
        self.storage = {}
        self.lock = threading.Lock()

    def _get_key(self, push_data: PushData):
        """ Generate a unique key based on app_session_id, entity_id, and attribute. """
        return push_data.app_session_id, push_data.entity_id, push_data.attribute

    def insert(self, push_data: PushData):
        """ Insert PushData into the storage. Replace if the new data has a later timestamp. """
        key = self._get_key(push_data)
        with self.lock:
            existing_data = self.storage.get(key)
            if existing_data is None or push_data.timestamp > existing_data.timestamp:
                self.storage[key] = push_data

    def get_by_app_session_id(self, app_session_id: str) -> List[PushData]:
        """ Get all PushData objects for a given app_session_id. """
        with self.lock:
            return [
                push_data for (stored_app_session_id, _, _), push_data in self.storage.items()
                if stored_app_session_id == app_session_id
            ]

    def decrease_delay(self):
        """
        Decrease the delay field in all PushData objects in storage by 1.
        Ensure delay never goes below 0.
        """
        with self.lock:
            for push_data in self.storage.values():
                push_data.delay = max(0, push_data.delay - 1)

    def remove_by_event_ids(self, app_session_id: str, event_ids: List[str]):
        """ Remove PushData objects from storage for the given list of event_ids within a specific app_session_id. """
        with self.lock:
            keys_to_remove = [
                key for key, push_data in self.storage.items()
                if key[0] == app_session_id and push_data.event_id in event_ids
            ]
            for key in keys_to_remove:
                self.storage.pop(key)

    def remove_by_app_session_id(self, app_session_id: str, *, entity_id: str | None = None):
        """
        Remove all PushData objects from storage for the given app_session_id.
        If entity_id is provided, remove only those matching both app_session_id and entity_id.
        """
        with self.lock:
            keys_to_remove = [
                key for key in self.storage.keys()
                if key[0] == app_session_id and (not entity_id or key[1] == entity_id)
            ]
            for key in keys_to_remove:
                self.storage.pop(key)

    def remove_by_app_session_ids(self, app_session_ids: [str]):
        """
        Remove all PushData objects from storage for the given list of app_session_ids.
        """
        with self.lock:
            keys_to_remove = [
                key for key in self.storage.keys()
                if key[0] in app_session_ids
            ]
            for key in keys_to_remove:
                self.storage.pop(key)

    def get_all_sorted(self) -> List[PushData]:
        """ Retrieve all PushData objects ordered by app_session_id and entity_id. """
        return sorted(self.storage.values(), key=lambda x: (x.push_session_id, x.entity_id))

    def process_entity_changes(
            self,
            app_sessions_data: dict,
            changed_entity_id: str,
            changed_attributes: dict,
            event_id: str,
            timestamp: int,
            context_id: str,
            delay: int
    ):
        """
        Processes changes for a given entity and its attributes, finds relevant app_sessions,
        and inserts PushData into the storage.

        Parameters:
        - app_sessions_data: dict of app_session subscription data.
        - changed_entity_id: The entity_id of the changed entity.
        - changed_attributes: A dictionary {attribute: new_value}.
        """
        for app_session_id, session_data in app_sessions_data.items():
            push_session_id = session_data.get('push_session_id')
            if not push_session_id:
                continue

            subscriptions = session_data.get("subscriptions", [])
            for subscription in subscriptions:
                entity_id = subscription["entity_id"]
                attribute = subscription["attribute"]
                need_push = subscription["need_push"]

                if need_push == 1 and entity_id == changed_entity_id:
                    if attribute in changed_attributes:
                        push_data = PushData(
                            event_id=event_id,
                            app_session_id=app_session_id,
                            push_session_id=push_session_id,
                            entity_id=entity_id,
                            attribute=attribute,
                            value=changed_attributes[attribute],
                            context_id=context_id,
                            timestamp=timestamp,
                            delay=delay,
                        )
                        # Insert PushData into storage
                        self.insert(push_data)

    def __str__(self):
        return "\n".join(str(data) for data in self.storage.values())


PUSHDATA_STORAGE: PushDataStorage = PushDataStorage()
