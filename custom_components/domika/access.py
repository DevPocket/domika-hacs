"""App session access checks."""

from homeassistant.components.websocket_api import ERR_UNAUTHORIZED, ActiveConnection

from .domika_logger import LOGGER
from .storage import APP_SESSIONS_STORAGE


def reject_foreign_session(
        connection: ActiveConnection,
        msg_id: int,
        app_session_id: str | None,
        *,
        allow_same_device: bool = False,
) -> bool:
    """
    Send an error and return True if the app session is owned by another user.

    Unknown app sessions are not rejected. With allow_same_device, a session that shares
    the push token hash with one of the user's sessions is accepted too.
    """
    user_id = connection.user.id
    if not app_session_id or not APP_SESSIONS_STORAGE.belongs_to_other_user(app_session_id, user_id):
        return False
    if allow_same_device and APP_SESSIONS_STORAGE.shares_device_with_user(app_session_id, user_id):
        return False

    LOGGER.warning(
        'Rejected msg_id=%s: app session "%s" belongs to another user (requested by user "%s")',
        msg_id,
        app_session_id,
        user_id,
    )
    connection.send_error(msg_id, ERR_UNAUTHORIZED, "App session belongs to another user")
    return True


def is_foreign_session(app_session_id: str, user_id: str) -> bool:
    """Return True and log if the app session is owned by another user."""
    if not APP_SESSIONS_STORAGE.belongs_to_other_user(app_session_id, user_id):
        return False
    LOGGER.warning(
        'Rejected HTTP request: app session "%s" belongs to another user (requested by user "%s")',
        app_session_id,
        user_id,
    )
    return True
