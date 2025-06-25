"""Critical sensor service."""

from typing import TYPE_CHECKING, Any, Iterable

from homeassistant.components import binary_sensor
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from ..const import (
    CRITICAL_NOTIFICATION_DEVICE_CLASSES,
    CRITICAL_PUSH_SETTINGS_DEVICE_CLASSES,
    DOMAIN,
    SENSORS_DOMAIN,
    WARNING_NOTIFICATION_DEVICE_CLASSES,
)
from ..domika_logger import LOGGER
from .enums import NotificationType
from .models import DomikaNotificationSensor, DomikaNotificationSensorsRead
from ..storage import USERS_STORAGE

if TYPE_CHECKING:
    from homeassistant.helpers.entity_registry import RegistryEntry

NOTIFICATION_TYPE_TO_CLASSES = {
    NotificationType.CRITICAL: CRITICAL_NOTIFICATION_DEVICE_CLASSES,
    NotificationType.WARNING: WARNING_NOTIFICATION_DEVICE_CLASSES,
}


def get(
    hass: HomeAssistant,
    notification_types: NotificationType,
) -> DomikaNotificationSensorsRead:
    """Get state of the critical sensors."""
    LOGGER.finer("Critical_sensor.service.get called, notification_types: %s", notification_types)

    result = DomikaNotificationSensorsRead([], [])

    entity_ids = hass.states.async_entity_ids(SENSORS_DOMAIN)
    entity_registry = er.async_get(hass)

    domain_data: dict[str, Any] | None = hass.data.get(DOMAIN)
    critical_entities = domain_data.get("critical_entities", {}) if domain_data else {}
    critical_included_entity_ids = critical_entities.get(
        "critical_included_entity_ids",
        [],
    )

    LOGGER.finer("Critical_sensor.service.get, critical_entities: %s, critical_included_entity_ids: %s",
                 critical_entities,
                 critical_included_entity_ids
                 )

    for entity_id in entity_ids:
        entity: RegistryEntry | None = entity_registry.entities.get(entity_id)
        if not entity or entity.hidden_by or entity.disabled_by:
            continue

        # If user manually added entity to the list for critical pushes — it's CRITICAL
        # for us.
        if entity_id in critical_included_entity_ids:
            sensor_notification_type = NotificationType.CRITICAL
        else:
            sensor_notification_type = notification_type(hass, entity_id)

        if not sensor_notification_type or sensor_notification_type not in notification_types:
            continue

        sensor_state: State | None = hass.states.get(entity_id)
        if not sensor_state:
            continue

        device_class: str | None = sensor_state.attributes.get(ATTR_DEVICE_CLASS)
        if not device_class:
            continue

        result.sensors.append(
            DomikaNotificationSensor(
                entity_id=entity_id,
                name=sensor_state.name,
                type=sensor_notification_type,
                device_class=device_class,
                state=sensor_state.state,
                timestamp=int(
                    max(
                        sensor_state.last_updated_timestamp,
                        sensor_state.last_changed_timestamp,
                    )
                    * 1e6,
                ),
            ),
        )
        if sensor_state.state == STATE_ON:
            result.sensors_on.append(entity_id)

    LOGGER.finer("Critical_sensor.service.get result: %s", result)
    return result


async def get_with_smiley(
    hass: HomeAssistant,
    notification_types: NotificationType,
    user_id: str,
    smiley_key: str,
    smiley_hash_key: str,
) -> dict:
    LOGGER.finer("Critical_sensor.service.get_with_smiley called, notification_types: %s, user_id: %s, " 
                 "smiley_key: %s, smiley_hash_key: %s",
                 notification_types,
                 user_id,
                 smiley_key,
                 smiley_hash_key)
    try:
        sensors_data = get(hass, notification_types)
        result = sensors_data.to_dict()

        key_value = USERS_STORAGE.get_users_data(user_id=user_id, key=smiley_key)

        if key_value:
            result[smiley_key] = key_value.value
            result[smiley_hash_key] = key_value.value_hash

        LOGGER.finer("Critical_sensor.service.get_with_smiley called, result: %s", result)
        return result
    except Exception:  # noqa: BLE001
        LOGGER.error(
            'Can\'t get value for key: %s, user "%s". Unhandled error',
            smiley_key,
            user_id,
        )


def check_notification_type(
    hass: HomeAssistant,
    entity_id: str,
    types: NotificationType,
) -> bool:
    """
    Check if entity is a binary sensor of certain notification types.

    Args:
        hass: homeassistant core object.
        entity_id: homeassistant entity id.
        types: wanted types flags.

    Returns:
        True if entity_id correspond to certain notification types, False otherwise.
    """
    if not entity_id.startswith(f"{binary_sensor.DOMAIN}."):
        return False

    domain_data: dict[str, Any] | None = hass.data.get(DOMAIN)
    critical_entities = domain_data.get("critical_entities", {}) if domain_data else {}
    critical_included_entity_ids = critical_entities.get(
        "critical_included_entity_ids",
        [],
    )
    # If user manually added entity to the list for critical pushes — it's CRITICAL for
    # us.
    if entity_id in critical_included_entity_ids and NotificationType.CRITICAL in types:
        return True

    sensor = hass.states.get(entity_id)
    if not sensor:
        return False

    sensor_class = sensor.attributes.get(ATTR_DEVICE_CLASS)

    return any(sensor_class in NOTIFICATION_TYPE_TO_CLASSES[level] for level in types)


def critical_push_needed(hass: HomeAssistant, entity_id: str) -> bool:
    """
    Check if user requested critical push notification for this binary sensor.

    Args:
        hass: homeassistant core object.
        entity_id: homeassistant entity id.

    Returns:
        True if user chose to get critical push notifications for this binary sensor,
        false otherwise.

    """
    if not entity_id.startswith(f"{binary_sensor.DOMAIN}."):
        return False

    domain_data: dict[str, Any] | None = hass.data.get(DOMAIN)
    critical_entities = domain_data.get("critical_entities", {}) if domain_data else {}
    critical_included_entity_ids = critical_entities.get(
        "critical_included_entity_ids",
        [],
    )
    # If user manually added entity to the list for critical pushes — return True.
    if entity_id in critical_included_entity_ids:
        return True

    sensor = hass.states.get(entity_id)
    if not sensor:
        return False

    sensor_class = sensor.attributes.get(ATTR_DEVICE_CLASS)

    critical_device_classes_enabled = []
    for key, value in critical_entities.items():
        if key in CRITICAL_PUSH_SETTINGS_DEVICE_CLASSES and value:
            critical_device_classes_enabled.append(
                CRITICAL_PUSH_SETTINGS_DEVICE_CLASSES[key],
            )

    return sensor_class in critical_device_classes_enabled


def critical_push_sensors_present(hass: HomeAssistant) -> bool:
    domain_data: dict[str, Any] | None = hass.data.get(DOMAIN)
    critical_entities = domain_data.get("critical_entities", {}) if domain_data else {}
    critical_included_entity_ids = critical_entities.get(
        "critical_included_entity_ids",
        [],
    )

    # If critical_included_entity_ids list is not empty — return True
    if critical_included_entity_ids:
        return True

    # If some device classes are enabled — return True
    for key, value in critical_entities.items():
        if key in CRITICAL_PUSH_SETTINGS_DEVICE_CLASSES and value:
            return True

    # Otherwise return False
    return False


def _send_critical_push_sensors_present_changed_events(
    hass: HomeAssistant,
    sensors_present: bool,
    app_session_ids: Iterable[str],
):
    for app_session in app_session_ids:
        data = {
                "d.type": "critical_push_sensors_present_changed",
                "critical_push_sensors_present": sensors_present,
            }
        hass.bus.async_fire(
            f"domika_{app_session}",
            data
        )
        LOGGER.finest(
            "critical_push_sensors_present_changed event fired: %s, data: %s"
            f"domika_{app_session}",
            data
        )


def notification_type(hass: HomeAssistant, entity_id: str) -> NotificationType | None:
    """
    Get notification type for binary sensor entity.

    Args:
        hass: homeassistant core object.
        entity_id: homeassistant entity id.

    Returns:
        Entity's notification type if applicable, None otherwise.

    """
    if not entity_id.startswith(f"{binary_sensor.DOMAIN}."):
        return None

    domain_data: dict[str, Any] | None = hass.data.get(DOMAIN)
    critical_entities = domain_data.get("critical_entities", {}) if domain_data else {}
    critical_included_entity_ids = critical_entities.get(
        "critical_included_entity_ids",
        [],
    )
    # If user manually added entity to the list for critical pushes — it's CRITICAL for
    # us.
    if entity_id in critical_included_entity_ids:
        return NotificationType.CRITICAL

    sensor = hass.states.get(entity_id)
    if not sensor:
        return None

    sensor_class = sensor.attributes.get(ATTR_DEVICE_CLASS)

    return next(
        (
            level
            for level in NotificationType.ANY
            if sensor_class in NOTIFICATION_TYPE_TO_CLASSES[level]
        ),
        None,
    )
