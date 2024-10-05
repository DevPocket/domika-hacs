# vim: set fileencoding=utf-8
"""
Application device.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

import json
import uuid

import aiohttp
import sqlalchemy
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .. import config, logger, errors, push_server_errors, statuses
from . import service as device_service
from .models import Device, DomikaDeviceCreate, DomikaDeviceUpdate


async def update_app_session_id(
    db_session: AsyncSession,
    app_session_id: uuid.UUID | None,
    user_id: str,
    push_token_hash: str,
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """
    Update or create app session id.

    If the session exists - updates its last_update and returns its id. Otherwise, it creates a new
    session and returns its id.

    Args:
        db_session: sqlalchemy session.
        app_session_id: Application session id.
        user_id: homeassistant user id.
        push_token_hash: hash of push_token+platform+environment.

    Returns:
        If the session exists - returns app_session_id. Otherwise, returns newly created session id.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    new_app_session_id: uuid.UUID | None = None

    if app_session_id:
        # Try to find the proper record.
        device = await device_service.get(db_session, app_session_id=app_session_id)

        if device:
            if device.user_id == user_id:
                # If found and user_id matches - update last_update.
                new_app_session_id = device.app_session_id
                stmt = sqlalchemy.update(Device)
                stmt = stmt.where(Device.app_session_id == new_app_session_id)
                stmt = stmt.values(last_update=func.datetime("now"))
                try:
                    await db_session.execute(stmt)
                    await db_session.commit()
                except SQLAlchemyError as e:
                    raise errors.DatabaseError(str(e)) from e
            else:
                # If found but user_id mismatch - remove app_session.
                logger.logger.debug(
                    "Update_app_session_id user_id mismatch: got %s, in db: %s.",
                    user_id,
                    device.user_id,
                )
                await device_service.delete(db_session, app_session_id)

    if not new_app_session_id:
        # If not found - create new one.
        device = await device_service.create(
            db_session,
            DomikaDeviceCreate(
                app_session_id=uuid.uuid4(),
                user_id=user_id,
                push_session_id=None,
                push_token_hash=push_token_hash,
            ),
        )
        new_app_session_id = device.app_session_id
        logger.logger.debug(
            "Update_app_session_id new app_session_id created: %s.",
            new_app_session_id,
        )

    result_old_app_sessions: list[uuid.UUID] = []
    if push_token_hash:
        old_devices = await device_service.get_all_with_push_token_hash(
            db_session,
            push_token_hash=push_token_hash,
        )
        result_old_app_sessions = [
            device.app_session_id
            for device in old_devices
            if device.app_session_id != new_app_session_id
        ]
    if result_old_app_sessions:
        logger.logger.debug(
            "Update_app_session_id result_old_app_sessions: %s.",
            result_old_app_sessions,
        )

    return new_app_session_id, result_old_app_sessions


async def remove_push_session(
    db_session: AsyncSession,
    http_session: aiohttp.ClientSession,
    app_session_id: uuid.UUID,
) -> uuid.UUID:
    """
    Remove push session from push server.

    Args:
        db_session: sqlalchemy session.
        http_session: aiohttp session.
        app_session_id: application session id.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
        errors.AppSessionIdNotFoundError: if app session not found.
        errors.PushSessionIdNotFoundError: if push session id not found on the integration.
        push_server_errors.PushSessionIdNotFoundError: if push session id not found on the push
        server.
        push_server_errors.BadRequestError: if push server response with bad request.
        push_server_errors.UnexpectedServerResponseError: if push server response with unexpected
        status.
    """
    device = await device_service.get(db_session, app_session_id)
    if not device:
        raise errors.AppSessionIdNotFoundError(app_session_id)

    if not device.push_session_id:
        raise errors.PushSessionIdNotFoundError(app_session_id)
    push_session_id = device.push_session_id

    try:
        await device_service.update(db_session, device, DomikaDeviceUpdate(push_session_id=None))
        async with (
            http_session.delete(
                f"{config.CONFIG.push_server_url}/push_session",
                headers={
                    # TODO: rename to x-push-session-id
                    "x-session-id": str(push_session_id),
                },
                timeout=config.CONFIG.push_server_timeout,
            ) as resp,
        ):
            if resp.status == statuses.HTTP_204_NO_CONTENT:
                logger.logger.debug(
                    "Remove_push_session deleted: %s.",
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
    push_token: str,
    app_session_id: str,
):
    """
    Initialize push session creation flow on the push server.

    Args:
        http_session: aiohttp session.
        original_transaction_id: original transaction id from the application.
        platform: application platform.
        environment: application environment.
        push_token: application push token.
        app_session_id: application push session id.

    Raises:
        ValueError: if original_transaction_id, push_token, platform or environment is empty.
        errors.DatabaseError: in case when database operation can't be performed.
        push_server_errors.BadRequestError: if push server response with bad request.
        push_server_errors.UnexpectedServerResponseError: if push server response with unexpected
        status.
    """
    if not (original_transaction_id and push_token and platform and environment and app_session_id):
        msg = "One of the parameters is missing"
        raise ValueError(msg)

    try:
        async with (
            http_session.post(
                f"{config.CONFIG.push_server_url}/push_session/create",
                json={
                    "original_transaction_id": original_transaction_id,
                    "platform": platform,
                    "environment": environment,
                    "push_token": push_token,
                    "app_session_id": app_session_id,
                },
                timeout=config.CONFIG.push_server_timeout,
            ) as resp,
        ):
            if resp.status == statuses.HTTP_202_ACCEPTED:
                return

            if resp.status == statuses.HTTP_400_BAD_REQUEST:
                raise push_server_errors.BadRequestError(await resp.json())

            raise push_server_errors.UnexpectedServerResponseError(resp.status)
    except aiohttp.ClientError as e:
        raise push_server_errors.DomikaPushServerError(str(e)) from None


async def verify_push_session(
    db_session: AsyncSession,
    http_session: aiohttp.ClientSession,
    app_session_id: uuid.UUID,
    verification_key: str,
    push_token_hash: str,
) -> uuid.UUID:
    """
    Finishes push session generation.

    After successful generation store new push session id for device with given app_session_id.

    Args:
        db_session: sqlalchemy session.
        http_session: aiohttp session.
        app_session_id: application session id.
        verification_key: verification key.
        push_token_hash: hash of the triplet (push_token, platform, environment)

    Raises:
        ValueError: if verification_key is empty.
        errors.DatabaseError: in case when database operation can't be performed.
        errors.AppSessionIdNotFoundError: if app session not found.
        push_server_errors.BadRequestError: if push server response with bad request.
        push_server_errors.UnexpectedServerResponseError: if push server response with unexpected
        status.
        push_server_errors.ResponseError: if push server response with malformed data.
    """
    if not verification_key:
        msg = "One of the parameters is missing"
        raise ValueError(msg)

    device = await device_service.get(db_session, app_session_id)
    if not device:
        raise errors.AppSessionIdNotFoundError(app_session_id)

    try:
        async with (
            http_session.post(
                f"{config.CONFIG.push_server_url}/push_session/verify",
                json={
                    "verification_key": verification_key,
                },
                timeout=config.CONFIG.push_server_timeout,
            ) as resp,
        ):
            if resp.status == statuses.HTTP_201_CREATED:
                try:
                    body = await resp.json()
                    push_session_id = uuid.UUID(body.get("push_session_id"))
                except json.JSONDecodeError as e:
                    raise push_server_errors.ResponseError(e) from None
                except ValueError:
                    msg = "Malformed push_session_id."
                    raise push_server_errors.ResponseError(msg) from None
                # Remove Devices with the same push_token_hash (if not empty), except current
                # device.
                if push_token_hash:
                    await device_service.remove_all_with_push_token_hash(
                        db_session,
                        push_token_hash,
                        device,
                    )
                # Update push_session_id and push_token_hash.
                await device_service.update(
                    db_session,
                    device,
                    DomikaDeviceUpdate(
                        push_session_id=push_session_id,
                        push_token_hash=push_token_hash,
                    ),
                )
                return push_session_id

            if resp.status == statuses.HTTP_400_BAD_REQUEST:
                raise push_server_errors.BadRequestError(await resp.json())

            if resp.status == statuses.HTTP_409_CONFLICT:
                raise push_server_errors.InvalidVerificationKeyError()

            raise push_server_errors.UnexpectedServerResponseError(resp.status)
    except aiohttp.ClientError as e:
        raise push_server_errors.DomikaPushServerError(str(e)) from None
