"""User event subscriptions flow functions."""

from contextlib import suppress

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import DatabaseError
from .models import DomikaSubscriptionCreate, DomikaSubscriptionUpdate
from .service import create, delete, get_subscription_map, update_in_place




# TODO: return more strict type
async def get_push_attributes(
        db_session: AsyncSession,
        app_session_id: str,
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

    # TODO STORAGE use storage here to return all subscriptions for this add_session_id with need_push = 1
    # we have get_app_session_subscriptions in Storage implemented
    # --- subscriptions = await get(db_session, app_session_id, need_push=True)

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
) -> set[str]:
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

    app_session_ids: set[str] = set()

    for attribute in attributes:
        with suppress(KeyError):
            app_session_ids.update(subscription_map[entity_id][attribute])

    return app_session_ids
