# vim: set fileencoding=utf-8
"""
Application device.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

import uuid
from typing import Sequence

import sqlalchemy
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import DatabaseError
from .models import Device, DomikaDeviceCreate, DomikaDeviceUpdate


async def get(db_session: AsyncSession, app_session_id: uuid.UUID) -> Device | None:
    """
    Get device by application session id.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = select(Device).where(Device.app_session_id == app_session_id)
    try:
        return await db_session.scalar(stmt)
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def get_all_with_push_session_id(db_session: AsyncSession) -> Sequence[Device]:
    """
    Get device by application session id.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = select(Device).where(Device.push_session_id.is_not(None))
    try:
        return (await db_session.scalars(stmt)).all()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def get_by_user_id(db_session: AsyncSession, user_id: str) -> Sequence[Device]:
    """
    Get device by user id.

    Raise:
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

    Raise:
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
    device: Device,
    *,
    commit: bool = True,
):
    """
    Remove all devices with the given push_token_hash.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = (
        sqlalchemy.delete(Device)
        .where(Device.push_token_hash == push_token_hash)
        .where(Device.app_session_id != device.app_session_id)
    )
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

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    device = Device(**device_in.to_dict())
    db_session.add(device)

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

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    device_data = device.dict()
    update_data = device_in.to_dict()

    for field in device_data:
        if field in update_data:
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

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.update(Device)
    stmt = stmt.where(Device.app_session_id == app_session_id)
    stmt = stmt.values(**device_in.to_dict())

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def delete(db_session: AsyncSession, app_session_id: uuid.UUID, *, commit: bool = True):
    """
    Delete device.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.delete(Device).where(Device.app_session_id == app_session_id)

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e
