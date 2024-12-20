"""HA entity service."""
from dataclasses import dataclass

from homeassistant.core import async_get_hass

from ..domika_logger import LOGGER
from ..utils import flatten_json
from ..storage import APP_SESSIONS_STORAGE


@dataclass
class DomikaHaEntity:
    """Base homeassistant entity state model."""
    entity_id: str
    time_updated: float
    attributes: dict[str, str]


async def get(
        app_session_id: str,
        *,
        need_push: bool | None = True,
        entity_id: str | None = None,
) -> list[DomikaHaEntity]:
    """
    Get the attribute state.

    Get the attribute state of all entities from the subscription for the given
    app_session_id.

    Filter by entity_id if passed and not None
    """
    LOGGER.finer("API.service.get called, app_session_id: %s, need_push: %s, entity_id: %s",
                 app_session_id,
                 need_push,
                 entity_id
                 )
    result: list[DomikaHaEntity] = []

    entities_attributes: dict[str, list[str]] = {}

    subscriptions = APP_SESSIONS_STORAGE.get_subscriptions(
        app_session_id,
        need_push=need_push,
        entity_id=entity_id,
    )

    # Convolve entities attribute in for of dict:
    # { noqa: ERA001
    #   "entity_id": ["attr1", "attr2"]
    # } noqa: ERA001
    for subscription in subscriptions:
        entities_attributes.setdefault(subscription.entity_id, []).append(
            subscription.attribute,
        )

    LOGGER.finer("API.service.get, entities_attributes: %s", entities_attributes)

    hass = async_get_hass()
    for entity, attributes in entities_attributes.items():
        state = hass.states.get(entity)
        if state:
            flat_state = flatten_json(
                state.as_compressed_state,
                exclude={"c", "lc", "lu"},
            )
            filtered_dict = {k: v for (k, v) in flat_state.items() if k in attributes}
            domika_entity = DomikaHaEntity(
                entity_id=entity,
                time_updated=max(state.last_changed, state.last_updated).timestamp(),
                attributes=filtered_dict,
            )
            result.append(
                domika_entity,
            )
        else:
            LOGGER.debug(
                'API.service.get is requesting state of unknown entity: "%s"',
                entity,
            )

    return result
