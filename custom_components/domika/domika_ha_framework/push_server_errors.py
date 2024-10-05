# vim: set fileencoding=utf-8
"""
Domika integration.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

import uuid

from .errors import DomikaFrameworkBaseError


class DomikaPushServerError(DomikaFrameworkBaseError):
    """Base push server error class."""


class ResponseError(DomikaPushServerError):
    """Push server response with data that can't be validated."""


class BadRequestError(DomikaPushServerError):
    """Push server replies with bad request."""

    def __init__(self, body: dict):
        super().__init__("Push server replies with bad request")
        self.body = body


class InvalidVerificationKeyError(DomikaPushServerError):
    """Push server reject verification key."""


class UnexpectedServerResponseError(DomikaPushServerError):
    """Push server replies with unexpected status."""

    def __init__(self, status: int):
        super().__init__(f"Push server replies with unexpected status {status}")
        self.status = status


class PushSessionIdNotFoundError(DomikaPushServerError):
    """Push session id found on the push server."""

    def __init__(self, push_session_id: uuid.UUID):
        super().__init__(f'Push session with id "{push_session_id}" not found on the push server')
        self.push_session_id = push_session_id


class PushTokenMismatchError(DomikaPushServerError):
    """
    Push token sent to the server does not match.

    Push token sent to the server does not match the one already registered on the server for this
    push session.
    """

    def __init__(self, push_token: str):
        super().__init__(
            f'Push token with id "{push_token}" does not match the one already'
            f"registered on the server",
        )
        self.push_token = push_token
