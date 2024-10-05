# vim: set fileencoding=utf-8
"""
Subscription data.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

import uuid
from collections.abc import Sequence
from dataclasses import asdict
from typing import Optional

import sqlalchemy
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import DatabaseError
from .models import DomikaSubscriptionCreate, DomikaSubscriptionUpdate, Subscription


async def get(
    db_session: AsyncSession,
    app_session_id: uuid.UUID,
    *,
    need_push: Optional[bool] = True,
    entity_id: Optional[str] = None,
) -> Sequence[Subscription]:
    """
    Get all subscriptions by application session id.

    Subscriptions filtered by need_push flag. If need_push is None no filtering applied.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.select(Subscription).where(Subscription.app_session_id == app_session_id)
    if need_push is not None:
        stmt = stmt.where(Subscription.need_push == need_push)
    if entity_id:
        stmt = stmt.where(Subscription.entity_id == entity_id)
    stmt = stmt.order_by(Subscription.entity_id).order_by(Subscription.attribute)

    try:
        return (await db_session.scalars(stmt)).all()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def create(
    db_session: AsyncSession,
    subscription_in: DomikaSubscriptionCreate,
    *,
    commit: bool = True,
):
    """
    Create new subscription.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    subscription = Subscription(**subscription_in.to_dict())
    db_session.add(subscription)

    try:
        await db_session.flush()
        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def update(
    db_session: AsyncSession,
    subscription: Subscription,
    subscription_in: DomikaSubscriptionUpdate,
    *,
    commit: bool = True,
):
    """
    Update subscription.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    subscription_attrs = subscription.dict()
    update_data = asdict(subscription_in)
    for attr in subscription_attrs:
        if attr in update_data:
            setattr(subscription, attr, update_data[attr])

    try:
        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def update_in_place(
    db_session: AsyncSession,
    app_session_id: uuid.UUID,
    entity_id: str,
    attribute: str,
    subscription_in: DomikaSubscriptionUpdate,
    *,
    commit: bool = True,
):
    """
    Update subscription in place.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.update(Subscription)
    stmt = stmt.where(Subscription.app_session_id == app_session_id)
    if entity_id:
        stmt = stmt.where(Subscription.entity_id == entity_id)
    if attribute:
        stmt = stmt.where(Subscription.attribute == attribute)
    stmt = stmt.values(**asdict(subscription_in))

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def delete(db_session: AsyncSession, app_session_id: uuid.UUID, *, commit: bool = True):
    """
    Delete subscription.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.delete(Subscription).where(Subscription.app_session_id == app_session_id)

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e
