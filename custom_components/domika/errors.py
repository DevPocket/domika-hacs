"""Domika homeassistant framework errors."""


class DomikaFrameworkBaseError(Exception):
    """Base error class."""



class AppSessionIdNotFoundError(DomikaFrameworkBaseError):
    """No app session id found."""

    def __init__(self, app_session_id: str):
        super().__init__(f'App session id "{app_session_id}" not found.')
        self.app_session_id = app_session_id


class PushSessionIdNotFoundError(DomikaFrameworkBaseError):
    """Push session id found on the integration."""

    def __init__(self, app_session_id: str):
        super().__init__(
            f'Push session id is missing for app session id "{app_session_id}".',
        )
        self.app_session_id = app_session_id
