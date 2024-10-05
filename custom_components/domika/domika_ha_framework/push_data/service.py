# vim: set fileencoding=utf-8
"""
Push data.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

import uuid
from collections.abc import Sequence
from typing import Optional

import sqlalchemy
import sqlalchemy.dialects.sqlite as sqlite_dialect
from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import DatabaseError
from ..subscription.models import Subscription
from .models import DomikaPushDataCreate, DomikaPushDataUpdate, PushData, _Event


async def get(
    db_session: AsyncSession,
    event_id: uuid.UUID,
) -> Sequence[PushData]:
    """
    Get push data by id.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.select(PushData).where(PushData.event_id == event_id)
    try:
        return (await db_session.scalars(stmt)).all()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def create(
    db_session: AsyncSession,
    events_in: list[DomikaPushDataCreate],
    *,
    commit: bool = True,
    returning: bool = False,
) -> Sequence[PushData]:
    """
    Create new push data.

    If already exists updates value and timestamp.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    result: Sequence[PushData] = []

    try:
        # Insert temporary homeassistant events.
        await db_session.execute(
            sqlalchemy.insert(_Event),
            [pd.to_dict() for pd in events_in],
        )
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e

    # Select events which need to be pushed.
    sel = sqlalchemy.select(
        _Event.event_id,
        Subscription.app_session_id,
        _Event.entity_id,
        _Event.attribute,
        _Event.value,
        _Event.context_id,
        _Event.timestamp,
        _Event.delay,
    )
    sel = sel.join(
        Subscription,
        (Subscription.entity_id == _Event.entity_id) & (Subscription.attribute == _Event.attribute),
    )
    sel = sel.where(
        Subscription.need_push.is_(True),
    )

    # Insert events that need to be pushed.
    stmt = sqlite_dialect.insert(PushData)
    stmt = stmt.from_select(
        [
            _Event.event_id,
            Subscription.app_session_id,
            _Event.entity_id,
            _Event.attribute,
            _Event.value,
            _Event.context_id,
            _Event.timestamp,
            _Event.delay,
        ],
        sel,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            PushData.app_session_id,
            PushData.entity_id,
            PushData.attribute,
        ],
        set_={
            "value": stmt.excluded.value,
            "timestamp": stmt.excluded.timestamp,
        },
    )

    try:
        if returning:
            stmt = stmt.returning(PushData)
            result = (await db_session.scalars(stmt)).all()
        else:
            await db_session.execute(stmt)

        # Remove temporary events.
        del_ = sqlalchemy.delete(_Event)
        await db_session.execute(del_)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e

    return result


async def update(
    db_session: AsyncSession,
    push_data: PushData,
    push_data_in: DomikaPushDataUpdate,
    *,
    commit: bool = True,
):
    """
    Update push data.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    push_data_attrs = push_data.dict()
    update_data = push_data_in.to_dict()

    for attr in push_data_attrs:
        if attr in update_data:
            setattr(push_data, attr, update_data[attr])

    try:
        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def delete(
    db_session: AsyncSession,
    event_id: uuid.UUID | list[uuid.UUID],
    app_session_id: uuid.UUID,
    *,
    commit: bool = True,
):
    """
    Delete push data by event id, or list of event id's.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    if isinstance(event_id, list):
        stmt = sqlalchemy.delete(PushData).where(
            and_(PushData.event_id.in_(event_id), PushData.app_session_id == app_session_id),
        )
    else:
        stmt = sqlalchemy.delete(PushData).where(
            and_(PushData.event_id == event_id, PushData.app_session_id == app_session_id),
        )

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def delete_all(
    db_session: AsyncSession,
    *,
    commit: bool = True,
):
    """
    Delete all push data.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.delete(PushData)

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def delete_by_app_session_id(
    db_session: AsyncSession,
    app_session_id: uuid.UUID | list[uuid.UUID],
    *,
    commit: bool = True,
):
    """
    Delete push data by event id, or list of event id's.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    if isinstance(app_session_id, list):
        stmt = sqlalchemy.delete(PushData).where(PushData.app_session_id.in_(app_session_id))
    else:
        stmt = sqlalchemy.delete(PushData).where(PushData.app_session_id == app_session_id)

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def decrease_delay_all(
    db_session: AsyncSession,
    *,
    commit: bool = True,
):
    """
    Decrease delay for all push data records with delay > 0.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.update(PushData)
    stmt = stmt.where(PushData.delay > 0)
    stmt = stmt.values(delay=PushData.delay - 1)

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def delete_for_app_session(
    db_session: AsyncSession,
    app_session_id: uuid.UUID,
    *,
    commit: bool = True,
    entity_id: Optional[str] = None,
):
    """
    Delete push data records for a certain app_session_id.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.delete(PushData).where(PushData.app_session_id == app_session_id)
    if entity_id:
        stmt = stmt.where(PushData.entity_id == entity_id)

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e
