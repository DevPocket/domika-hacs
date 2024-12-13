"""App sessions storage module."""

from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import datetime
from typing import Any, List

from .models import AppSession, Subscription
from homeassistant.helpers.storage import Store
from ..const import DOMAIN, LOGGER, DEVICE_INACTIVITY_TIME_THRESHOLD, DEVICE_INACTIVITY_CHECK_INTERVAL

STORAGE_VERSION_APP_SESSIONS = 1
STORAGE_KEY_APP_SESSIONS = f"{DOMAIN}/app_sessions_storage.json"

APP_SESSIONS_LOCK = threading.Lock()


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