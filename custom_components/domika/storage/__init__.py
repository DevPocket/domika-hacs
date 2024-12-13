"""Storage module."""

from users_storage import UsersStorage
from app_sessions_storage import AppSessionsStorage

USERS_STORAGE: UsersStorage = UsersStorage()
APP_SESSIONS_STORAGE: AppSessionsStorage = AppSessionsStorage()


async def init_storage(hass):
    await USERS_STORAGE.load_data(hass)
    await APP_SESSIONS_STORAGE.load_data(hass)