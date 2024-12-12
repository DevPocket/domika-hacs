"""User event subscriptions service functions."""

from collections.abc import Sequence
from dataclasses import asdict
from typing import overload

import sqlalchemy
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import cached
from ..database import core as database_core
from ..errors import DatabaseError
from ..utils import cache_key_ignore_first_arg
from .models import (
    DomikaSubscriptionCreate,
    DomikaSubscriptionUpdate,
    Subscription,
    SubscriptionMap,
)



async def get_all(
    db_session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    *,
    need_push: bool | None = True,
    entity_id: str | None = None,
) -> Sequence[Subscription]:
    """
    Get all subscriptions by application session id.

    Subscriptions filtered by need_push flag. If need_push is None no filtering applied.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.select(Subscription).order_by(
        Subscription.app_session_id,
        Subscription.entity_id,
        Subscription.attribute,
    )
    if need_push is not None:
        stmt = stmt.where(Subscription.need_push == need_push)
    if entity_id:
        stmt = stmt.where(Subscription.entity_id == entity_id)
    stmt = stmt.limit(limit).offset(offset)

    try:
        return (await db_session.scalars(stmt)).all()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


@overload
async def get_subscription_map() -> SubscriptionMap: ...


@overload
async def get_subscription_map(db_session: AsyncSession) -> SubscriptionMap: ...


@cached(cache_key_ignore_first_arg)
async def get_subscription_map(
    db_session: AsyncSession | None = None,
) -> SubscriptionMap:
    """
    Get all subscriptions, and build subscription map.

    ```md
    Build subscription map that looks like:
    ├── entity_1
    │   ├── attribute_1
    │   │   ├── app_session_1
    │   │   └── app_session_2
    │   └── attribute_2
    │       └── app_session_3
    └── entity_2
        └── attribute_1
            └── app_session_2
    ```

    If cached value exists - return cached value.
    If db_session is not set - create database session implicitly.

    Args:
        db_session: optional sqlalchemy database session. Defaults to None.

    Returns:
        Subscription map.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    if db_session is None:
        async with database_core.get_session() as db_session_:
            return await get_subscription_map(db_session_)

    subscription_map: SubscriptionMap = {}

    offset = 0
    limit = 500
    while True:
        chunk = await get_all(db_session, limit=limit, offset=offset, need_push=None)
        chunk_size = len(chunk)
        offset += chunk_size

        for subscription in chunk:
            attributes_map = subscription_map.get(subscription.entity_id)
            if attributes_map is None:
                attributes_map = subscription_map[subscription.entity_id] = {}

            app_session_ids = attributes_map.get(subscription.attribute)
            if app_session_ids is None:
                app_session_ids = attributes_map[subscription.attribute] = set()

            app_session_ids.add(subscription.app_session_id)

        if chunk_size < limit:
            break

    return subscription_map


async def create(
    db_session: AsyncSession,
    subscription_in: DomikaSubscriptionCreate,
    *,
    commit: bool = True,
):
    """
    Create new subscription.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    subscription = Subscription(**subscription_in.to_dict())
    db_session.add(subscription)

    get_subscription_map.cache_clear()

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

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    subscription_attrs = subscription.dict()
    update_data = asdict(subscription_in)
    for attr in subscription_attrs:
        if attr in update_data:
            setattr(subscription, attr, update_data[attr])

    get_subscription_map.cache_clear()

    try:
        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def update_in_place(
    db_session: AsyncSession,
    app_session_id: str,
    entity_id: str,
    attribute: str,
    subscription_in: DomikaSubscriptionUpdate,
    *,
    commit: bool = True,
):
    """
    Update subscription in place.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.update(Subscription)
    stmt = stmt.where(Subscription.app_session_id == app_session_id)
    if entity_id:
        stmt = stmt.where(Subscription.entity_id == entity_id)
    if attribute:
        stmt = stmt.where(Subscription.attribute == attribute)
    stmt = stmt.values(**asdict(subscription_in))

    get_subscription_map.cache_clear()

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def delete(
    db_session: AsyncSession,
    app_session_id: str,
    *,
    commit: bool = True,
):
    """
    Delete subscription.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.delete(Subscription).where(
        Subscription.app_session_id == app_session_id,
    )

    get_subscription_map.cache_clear()

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e
