"""Application sessions flow functions."""

import json

import aiohttp
from ..domika_logger import LOGGER

from .. import errors, push_server_errors, statuses
from ..storage import APP_SESSIONS_STORAGE


async def remove_push_session(
        http_session: aiohttp.ClientSession,
        app_session_id: str,
        push_server_url: str,
        push_server_timeout: aiohttp.ClientTimeout,
) -> str:
    """
    Remove push session from push server.

    Args:
        http_session: aiohttp session.
        app_session_id: application session id.
        push_server_url: domika push server url.
        push_server_timeout: domika push server response timeout.

    Raises:
        errors.AppSessionIdNotFoundError: if app session not found.
        errors.PushSessionIdNotFoundError: if push session id not found on the
            integration.
        push_server_errors.PushSessionIdNotFoundError: if push session id not found on
            the push server.
        push_server_errors.BadRequestError: if push server response with bad request.
        push_server_errors.UnexpectedServerResponseError: if push server response with
            unexpected status.
    """
    LOGGER.finer("Sessions.remove_push_session started")
    app_session = APP_SESSIONS_STORAGE.get_app_session(app_session_id)
    if not app_session:
        raise errors.AppSessionIdNotFoundError(app_session_id)

    if not app_session.push_session_id:
        raise errors.PushSessionIdNotFoundError(app_session_id)
    push_session_id = app_session.push_session_id

    try:
        APP_SESSIONS_STORAGE.remove_push_session(app_session_id)

        async with (
            http_session.delete(
                f"{push_server_url}/push_session",
                headers={
                    # TODO: rename to x-push-session-id
                    "x-session-id": push_session_id,
                },
                timeout=push_server_timeout,
            ) as resp,
        ):
            if resp.status == statuses.HTTP_204_NO_CONTENT:
                LOGGER.debug(
                    "Remove_push_session deleted: %s",
                    push_session_id,
                )
                return push_session_id

            if resp.status == statuses.HTTP_400_BAD_REQUEST:
                raise push_server_errors.BadRequestError(await resp.json())

            if resp.status == statuses.HTTP_401_UNAUTHORIZED:
                raise push_server_errors.PushSessionIdNotFoundError(push_session_id)

            raise push_server_errors.UnexpectedServerResponseError(resp.status)
    except aiohttp.ClientError as e:
        raise push_server_errors.DomikaPushServerError(str(e)) from None


async def create_push_session(
        http_session: aiohttp.ClientSession,
        original_transaction_id: str,
        platform: str,
        environment: str,
        transaction_environment: str,
        push_token: str,
        app_session_id: str,
        push_server_url: str,
        push_server_timeout: aiohttp.ClientTimeout,
):
    """
    Initialize push session creation flow on the push server.

    Args:
        http_session: aiohttp session.
        original_transaction_id: original transaction id from the application.
        platform: application platform.
        environment: environment for push notifications.
        transaction_environment: environment for purchase verification.
        push_token: application push token.
        app_session_id: application push session id.
        push_server_url: domika push server url.
        push_server_timeout: domika push server response timeout.

    Raises:
        ValueError: if original_transaction_id, push_token, platform or environment is
            empty.
        push_server_errors.BadRequestError: if push server response with bad request.
        push_server_errors.UnexpectedServerResponseError: if push server response with
            unexpected status.
    """
    LOGGER.finer("Sessions.create_push_session started")
    if not (
            original_transaction_id
            and push_token
            and platform
            and environment
            and transaction_environment
            and app_session_id
    ):
        msg = "One of the parameters is missing"
        raise ValueError(msg)

    try:
        async with (
            http_session.post(
                f"{push_server_url}/push_session/create",
                json={
                    "original_transaction_id": original_transaction_id,
                    "platform": platform,
                    "environment": environment,
                    "transaction_environment": transaction_environment,
                    "push_token": push_token,
                    "app_session_id": app_session_id,
                },
                timeout=push_server_timeout,
            ) as resp,
        ):
            if resp.status == statuses.HTTP_202_ACCEPTED:
                LOGGER.finer("Sessions.create_push_session sent to push server")
                return

            if resp.status == statuses.HTTP_400_BAD_REQUEST:
                raise push_server_errors.BadRequestError(await resp.json())

            raise push_server_errors.UnexpectedServerResponseError(resp.status)
    except aiohttp.ClientError as e:
        raise push_server_errors.DomikaPushServerError(str(e)) from None


async def verify_push_session(
        http_session: aiohttp.ClientSession,
        app_session_id: str,
        verification_key: str,
        push_token_hash: str,
        push_server_url: str,
        push_server_timeout: aiohttp.ClientTimeout,
) -> str:
    """
    Finishes push session generation.

    After successful generation store new push session id for sessions with given
    app_session_id.

    Args:
        http_session: aiohttp session.
        app_session_id: application session id.
        verification_key: verification key.
        push_token_hash: hash of the triplet (push_token, platform, environment).
        push_server_url: domika push server url.
        push_server_timeout: domika push server response timeout.

    Raises:
        ValueError: if verification_key is empty.
        errors.DatabaseError: in case when database operation can't be performed.
        errors.AppSessionIdNotFoundError: if app session not found.
        push_server_errors.BadRequestError: if push server response with bad request.
        push_server_errors.UnexpectedServerResponseError: if push server response with
            unexpected status.
        push_server_errors.ResponseError: if push server response with malformed data.
    """
    LOGGER.finer("Sessions.verify_push_session started")
    if not verification_key:
        msg = "One of the parameters is missing"
        raise ValueError(msg)

    app_session = APP_SESSIONS_STORAGE.get_app_session(app_session_id)
    if not app_session:
        raise errors.AppSessionIdNotFoundError(app_session_id)

    try:
        async with (
            http_session.post(
                f"{push_server_url}/push_session/verify",
                json={
                    "verification_key": verification_key,
                },
                timeout=push_server_timeout,
            ) as resp,
        ):
            if resp.status == statuses.HTTP_201_CREATED:
                try:
                    body = await resp.json()
                    push_session_id = body.get("push_session_id")
                except json.JSONDecodeError as e:
                    raise push_server_errors.ResponseError(e) from None
                except ValueError:
                    msg = "Malformed push_session_id."
                    raise push_server_errors.ResponseError(msg) from None
                # Remove Devices with the same push_token_hash (if not empty), except
                # current sessions.
                if push_token_hash:
                    APP_SESSIONS_STORAGE.remove_all_with_push_token_hash(
                        push_token_hash,
                        app_session_id,
                    )
                # Update push_session_id and push_token_hash.
                APP_SESSIONS_STORAGE.update_push_session(app_session_id, push_session_id, push_token_hash)
                return push_session_id

            if resp.status == statuses.HTTP_400_BAD_REQUEST:
                raise push_server_errors.BadRequestError(await resp.json())

            if resp.status == statuses.HTTP_409_CONFLICT:
                raise push_server_errors.InvalidVerificationKeyError()

            raise push_server_errors.UnexpectedServerResponseError(resp.status)
    except aiohttp.ClientError as e:
        raise push_server_errors.DomikaPushServerError(str(e)) from None
