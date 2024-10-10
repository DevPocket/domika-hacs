"""User event subscriptions flow functions."""

from contextlib import suppress
import uuid

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import DatabaseError
from .models import DomikaSubscriptionCreate, DomikaSubscriptionUpdate
from .service import create, delete, get, get_subscription_map, update_in_place


# TODO: maybe reorganize data so it can support schemas.
async def resubscribe(
    db_session: AsyncSession,
    app_session_id: uuid.UUID,
    subscriptions: dict[str, dict[str, int]],
):
    """
    Remove all existing subscriptions, and subscribe to the new subscriptions.

    Raises:
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

    Set need_push to true for given entities attributes, for all other set need_push to
    false.

    Raises:
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


# TODO: return more strict type
async def get_push_attributes(
    db_session: AsyncSession,
    app_session_id: uuid.UUID,
) -> list:
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

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    result = []

    subscriptions = await get(db_session, app_session_id, need_push=True)

    entity_attributes: dict = {}
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
            entity_attributes["attributes"].append(subscription.attribute)

    return result


async def get_app_session_id_by_attributes(
    entity_id: str,
    attributes: list[str],
) -> set[uuid.UUID]:
    """
    Get app session id's subscribed for entity attribute changes.

    Get all app session id's for which given entity_id contains attribute from
    attributes.

    Args:
        entity_id: homeassistant entity id.
        attributes: entity's attributes to search.

    Returns:
        App session id's.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    subscription_map = await get_subscription_map()

    app_session_ids: set[uuid.UUID] = set()

    for attribute in attributes:
        with suppress(KeyError):
            app_session_ids.update(subscription_map[entity_id][attribute])

    return app_session_ids
