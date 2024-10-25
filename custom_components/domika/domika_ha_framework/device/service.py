"""Application device service functions."""

from collections.abc import Sequence
import datetime
from typing import overload
import uuid

import sqlalchemy
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import cached
from ..database import core as database_core
from ..errors import DatabaseError
from ..utils import cache_key_ignore_first_arg
from .models import Device, DomikaDeviceCreate, DomikaDeviceUpdate


async def get(db_session: AsyncSession, app_session_id: uuid.UUID) -> Device | None:
    """
    Get device by application session id.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = select(Device).where(Device.app_session_id == app_session_id)
    try:
        return await db_session.scalar(stmt)
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def get_all(
    db_session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Device]:
    """
    Get all devices.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = (
        sqlalchemy.select(Device)
        .order_by(Device.app_session_id)
        .limit(limit)
        .offset(offset)
    )
    try:
        return (await db_session.scalars(stmt)).all()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


@overload
async def get_all_with_push_session_id() -> Sequence[Device]: ...


@overload
async def get_all_with_push_session_id(
    db_session: AsyncSession,
) -> Sequence[Device]: ...


@cached(cache_key_ignore_first_arg)
async def get_all_with_push_session_id(
    db_session: AsyncSession | None = None,
) -> Sequence[Device]:
    """
    Get all devices which have push_session_id.

    If cached value exists - return cached value, load and return cached otherwise.
    Returned ORM objects are not bound to any database session. So you can't use them
    for database manipulation. If you need bound objects use .without_cache() from this
    function.

    If db_session is not set - create database session implicitly, .without_cache() make
    no sense in this case.

    Args:
        db_session: optional sqlalchemy database session. Defaults to None.

    Raises:
        DatabaseError: in case when database operation can't be performed.

    Returns:
        All devices which have push_session_id set.
    """
    if db_session is None:
        async with database_core.get_session() as db_session_:
            return await get_all_with_push_session_id(db_session_)

    stmt = select(Device).where(Device.push_session_id.is_not(None))
    try:
        return (await db_session.scalars(stmt)).all()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def get_by_user_id(db_session: AsyncSession, user_id: str) -> Sequence[Device]:
    """
    Get device by user id.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = select(Device).where(Device.user_id == user_id)
    try:
        return (await db_session.scalars(stmt)).all()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def get_all_with_push_token_hash(
    db_session: AsyncSession,
    push_token_hash: str,
) -> Sequence[Device]:
    """
    Get all devices with given push_token_hash.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = select(Device).where(Device.push_token_hash == push_token_hash)
    try:
        return (await db_session.scalars(stmt)).all()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def remove_all_with_push_token_hash(
    db_session: AsyncSession,
    push_token_hash: str,
    except_device: Device,
    *,
    commit: bool = True,
):
    """
    Remove all devices with the given push_token_hash.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = (
        sqlalchemy.delete(Device)
        .where(Device.push_token_hash == push_token_hash)
        .where(Device.app_session_id != except_device.app_session_id)
    )

    # Cleanup cache.
    get_all_with_push_session_id.cache_clear()

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def create(
    db_session: AsyncSession,
    device_in: DomikaDeviceCreate,
    *,
    commit: bool = True,
) -> Device:
    """
    Create new device.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    device = Device(**device_in.to_dict())
    db_session.add(device)

    # Cleanup cache.
    get_all_with_push_session_id.cache_clear()

    try:
        await db_session.flush()

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e

    return device


async def update(
    db_session: AsyncSession,
    device: Device,
    device_in: DomikaDeviceUpdate,
    *,
    commit: bool = True,
) -> Device:
    """
    Update device model.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    device_data = device.dict()
    update_data = device_in.to_dict()

    for field in device_data:
        if field in update_data:
            if field == "push_session_id":
                # Cleanup cache.
                get_all_with_push_session_id.cache_clear()
            setattr(device, field, update_data[field])

    try:
        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e

    return device


async def update_in_place(
    db_session: AsyncSession,
    app_session_id: uuid.UUID,
    device_in: DomikaDeviceUpdate,
    *,
    commit: bool = True,
):
    """
    Update device in place.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.update(Device)
    stmt = stmt.where(Device.app_session_id == app_session_id)
    update_data = device_in.to_dict()
    if "push_session_id" in update_data:
        # Cleanup cache.
        get_all_with_push_session_id.cache_clear()
    stmt = stmt.values(**update_data)

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def delete(
    db_session: AsyncSession,
    app_session_id: uuid.UUID,
    *,
    commit: bool = True,
):
    """
    Delete device.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.delete(Device).where(Device.app_session_id == app_session_id)

    # Cleanup cache.
    get_all_with_push_session_id.cache_clear()

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def delete_inactive(
    db_session: AsyncSession,
    inactivity_threshold: datetime.timedelta,
    *,
    commit: bool = True,
):
    """
    Delete inactive device.

    Args:
        db_session: sqlalchemy database session.
        inactivity_threshold: time after which the device is considered inactive.
        commit: commit after deletion.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.delete(Device).where(
        Device.last_update
        < func.datetime("now", f"-{inactivity_threshold.total_seconds()} seconds"),
    )

    # Cleanup cache.
    get_all_with_push_session_id.cache_clear()

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e
