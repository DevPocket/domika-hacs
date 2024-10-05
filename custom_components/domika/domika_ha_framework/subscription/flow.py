# vim: set fileencoding=utf-8
"""
Subscription data.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

import uuid
from typing import Sequence

import sqlalchemy
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import DatabaseError
from .models import DomikaSubscriptionCreate, DomikaSubscriptionUpdate, Subscription
from .service import create, delete, get, update_in_place


# TODO: maybe reorganize data so it can support schemas.
async def resubscribe(
    db_session: AsyncSession,
    app_session_id: uuid.UUID,
    subscriptions: dict[str, dict[str, int]],
):
    """
    Remove all existing subscriptions, and subscribe to the new subscriptions.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    await delete(db_session, app_session_id, commit=False)
    for entity, attrs in subscriptions.items():
        for attr_name, need_push in attrs.items():
            # TODO: create_many
            await create(
                db_session,
                DomikaSubscriptionCreate(
                    app_session_id=app_session_id,
                    entity_id=entity,
                    attribute=attr_name,
                    need_push=bool(need_push),
                ),
                commit=False,
            )
    try:
        await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


# TODO: maybe reorganize data so it can support schemas.
async def resubscribe_push(
    db_session: AsyncSession,
    app_session_id: uuid.UUID,
    subscriptions: dict[str, set[str]],
):
    """
    Set need_push for given app_session_id.

    Set need_push to true for given entities attributes, for all other set need_push to false.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    await update_in_place(
        db_session,
        app_session_id,
        entity_id="",
        attribute="",
        subscription_in=DomikaSubscriptionUpdate(need_push=False),
        commit=False,
    )
    for entity, attrs in subscriptions.items():
        for attr in attrs:
            # TODO: update_many
            await update_in_place(
                db_session,
                app_session_id=app_session_id,
                entity_id=entity,
                attribute=attr,
                subscription_in=DomikaSubscriptionUpdate(need_push=True),
                commit=False,
            )
    try:
        await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def get_push_attributes(db_session: AsyncSession, app_session_id: uuid.UUID) -> list:
    """
    Return list of entity_id grouped with their attributes for given app session id.

    Example:
        [
            {
                "entity_id": "id1",
                "attributes": ["a1", "a2"]
            },
            {
                "entity_id": "id2",
                "attributes": ["a21", "a22"]
            },
        ]

    Args:
        db_session: sqlalchemy session.
        app_session_id: application session id.

    Returns:
        list of entity_id grouped with their attributes.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    result = []

    subscriptions = await get(db_session, app_session_id, need_push=True)

    entity_attributes: dict | None = None
    current_entity: str | None = None
    for subscription in subscriptions:
        if current_entity != subscription.entity_id:
            entity_attributes = {
                "entity_id": subscription.entity_id,
                "attributes": [subscription.attribute],
            }
            result.append(entity_attributes)
            current_entity = subscription.entity_id
        else:
            # entity_attributes always exists in this case.
            entity_attributes["attributes"].append(subscription.attribute)  # type: ignore

    return result


async def get_app_session_id_by_attributes(
    db_session: AsyncSession,
    entity_id: str,
    attributes: list[str],
) -> Sequence[uuid.UUID]:
    """
    Get all app session id's for with given entity_id that contains attribute from attributes.

    Args:
        db_session: sqlalchemy session.
        entity_id: homeassistant entity id.
        attributes: entity's attributes to search.

    Returns:
        app session id's for with given entity_id that contains attribute from attributes

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.select(Subscription.app_session_id)
    stmt = stmt.distinct(Subscription.app_session_id)
    stmt = stmt.where(
        Subscription.entity_id == entity_id,
        Subscription.attribute.in_(attributes),
    )
    try:
        return (await db_session.scalars(stmt)).all()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e
