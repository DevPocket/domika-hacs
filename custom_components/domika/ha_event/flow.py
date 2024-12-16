"""HA event flow."""

from collections.abc import Iterable
import uuid
import json

from aiohttp import ClientTimeout, ClientSession, ClientError

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import (
    CompressedState,
    Event,
    EventStateChangedData,
    HomeAssistant,
)

from .. import statuses, push_server_errors
from ..const import (
    CRITICAL_PUSH_ALERT_STRINGS,
    PUSH_DELAY_DEFAULT,
    PUSH_DELAY_FOR_DOMAIN,
    PUSH_SERVER_TIMEOUT,
    PUSH_SERVER_URL,
)
from ..domika_logger import LOGGER
from ..critical_sensor import service as critical_sensor_service
from ..critical_sensor.enums import NotificationType
from ..push_data_storage.pushdatastorage import PUSHDATA_STORAGE
from ..utils import flatten_json
from ..storage import APP_SESSIONS_STORAGE


async def register_event(
        hass: HomeAssistant,
        event: Event[EventStateChangedData],
) -> None:
    """Register new incoming HA event."""
    event_data: EventStateChangedData = event.data
    entity_id = event_data["entity_id"]
    attributes = _get_changed_attributes_from_event_data(event_data)

    LOGGER.trace(
        "register_event entity_id: %s, attributes: %s, time fired: %s",
        entity_id,
        attributes,
        event.time_fired,
    )

    if not attributes:
        return

    # Check if it's a critical or warning binary sensor.
    notification_required = critical_sensor_service.check_notification_type(
        hass,
        entity_id,
        NotificationType.ANY,
    )
    LOGGER.fine(
        "register_event entity_id: %s, notification_required: %s",
        entity_id,
        notification_required
    )

    # Fire event for application if important sensor changed it's state.
    if notification_required:
        _fire_critical_sensor_notification(
            hass,
            event,
        )

    event_id = str(uuid.uuid4())

    critical_push_needed = (
            critical_sensor_service.critical_push_needed(hass, entity_id)
            and attributes.get("s") == "on"
    )

    critical_alert_payload = (
        _get_critical_alert_payload(hass, entity_id) if critical_push_needed else {}
    )

    LOGGER.finest(
        "register_event entity_id: %s, critical_push_needed: %s, critical_alert_payload: %s",
        entity_id,
        critical_push_needed,
        critical_alert_payload
    )
    # Get application id's associated with attributes.
    app_session_ids = APP_SESSIONS_STORAGE.get_app_sessions_for_event(
        entity_id=entity_id,
        attributes=list(attributes.keys())
    )
    LOGGER.finest(
        "register_event entity_id: %s, app_session_ids: %s",
        entity_id,
        app_session_ids
    )
    # If any app_session_ids are subscribed for these attributes - fire the event
    # to those app_session_ids for app to catch.
    if app_session_ids:
        _fire_event_to_app_session_ids(
            hass,
            event,
            event_id,
            entity_id,
            attributes,
            app_session_ids,
        )

    # Process event to push_data_storage
    delay = await _get_delay_by_entity_id(hass, entity_id)
    LOGGER.finest(
        "register_event entity_id: %s, delay: %s",
        entity_id,
        delay
    )
    PUSHDATA_STORAGE.process_entity_changes(
        push_subscriptions=APP_SESSIONS_STORAGE.push_subscriptions(),
        changed_entity_id=entity_id,
        changed_attributes=attributes,
        event_id=event_id,
        timestamp=int(event.time_fired_timestamp),
        context_id=event.context.id,
        delay=delay
    )

    if critical_push_needed:
        app_sessions_with_push_session = APP_SESSIONS_STORAGE.get_app_sessions_with_push_session()

        # TODO: remove!
        # await process_push_data(hass)

        LOGGER.finest(
            "register_event entity_id: %s, app_sessions_with_push_session: %s",
            entity_id,
            app_sessions_with_push_session
        )
        for item in app_sessions_with_push_session:
            await _send_push_data(
                async_get_clientsession(hass),
                PUSH_SERVER_URL,
                PUSH_SERVER_TIMEOUT,
                item.app_session_id,
                item.push_session_id,
                critical_alert_payload,
                critical=True,
            )


def _get_critical_alert_payload(hass: HomeAssistant, entity_id: str) -> dict:
    """Create the payload for a critical push."""
    alert_title = CRITICAL_PUSH_ALERT_STRINGS.get("default", "")
    alert_body = hass.config.location_name

    entity = hass.states.get(entity_id)
    if entity:
        entity_class = entity.attributes.get(ATTR_DEVICE_CLASS)
        if entity_class:
            alert_title = CRITICAL_PUSH_ALERT_STRINGS.get(entity_class, "")

        alert_body = f"{entity.name}, " + alert_body

    return {"title-loc-key": alert_title, "body": alert_body}


async def process_push_data(hass: HomeAssistant) -> None:
    """
    Push registered events with delay = 0 to the push server.

    Select push data with delay = 0, add push data with delay > 0 for the same
    app_session_ids, create formatted push data, send it to the push server api,
    delete all processed push data.

    Raises:
        push_server_errors.DomikaPushServerError: in case of internal aiohttp error.
        push_server_errors.BadRequestError: if push server response with bad request.
        push_server_errors.UnexpectedServerResponseError: if push server response with
            unexpected status.
    """
    LOGGER.debug("process_push_data started")

    PUSHDATA_STORAGE.decrease_delay()
    push_data_records = PUSHDATA_STORAGE.get_all_sorted()

    # Create push data dict.
    # Format example:
    # '{
    # '  "binary_sensor.smoke": {
    # '    "s": {
    # '       "v": "on",
    # '       "t": 717177272
    # '     }
    # '  },
    # '  "light.light": {
    # '    "s": {
    # '       "v": "off",
    # '       "t": 717145367
    # '     }
    # '  },
    # '}

    app_sessions_ids_to_delete_list: list[str] = []
    events_dict = {}
    current_entity_id: str | None = None
    current_push_session_id: str | None = None
    current_app_session_id: str | None = None
    found_delay_zero: bool = False

    entity = {}
    for push_data_record in push_data_records:
        if current_app_session_id != push_data_record.app_session_id:
            if (
                    found_delay_zero
                    and events_dict
                    and current_push_session_id
                    and current_app_session_id
            ):
                await _send_push_data(
                    async_get_clientsession(hass),
                    PUSH_SERVER_URL,
                    PUSH_SERVER_TIMEOUT,
                    current_app_session_id,
                    current_push_session_id,
                    events_dict,
                )
                app_sessions_ids_to_delete_list.append(current_app_session_id)
            current_push_session_id = push_data_record.push_session_id
            current_app_session_id = push_data_record.app_session_id
            current_entity_id = None
            events_dict = {}
            found_delay_zero = False
        if current_entity_id != push_data_record.entity_id:
            entity = {}
            events_dict[push_data_record.entity_id] = entity
            current_entity_id = push_data_record.entity_id
        entity[push_data_record.attribute] = {
            "v": push_data_record.value,
            "t": push_data_record.timestamp,
        }
        found_delay_zero = found_delay_zero or (push_data_record.delay == 0)

    if (
            found_delay_zero
            and events_dict
            and current_push_session_id
            and current_app_session_id
    ):
        await _send_push_data(
            async_get_clientsession(hass),
            PUSH_SERVER_URL,
            PUSH_SERVER_TIMEOUT,
            current_app_session_id,
            current_push_session_id,
            events_dict
        )
        app_sessions_ids_to_delete_list.append(current_app_session_id)

    PUSHDATA_STORAGE.remove_by_app_session_ids(app_sessions_ids_to_delete_list)


async def _send_push_data(
        http_session: ClientSession,
        push_server_url: str,
        push_server_timeout: ClientTimeout,
        app_session_id: str,
        push_session_id: str,
        payload: dict,
        *,
        critical: bool = False,
) -> None:
    LOGGER.verbose("Push events %s to push_session %s (app_session %s). %s",
        "(critical)" if critical else " ",
        push_session_id,
        app_session_id,
        payload
    )

    try:
        async with (
            http_session.post(
                f"{push_server_url}/notification/critical_push"
                if critical
                else f"{push_server_url}/notification/push",
                headers={
                    "x-session-id": str(push_session_id),
                },
                json={"data": json.dumps(payload)},
                timeout=push_server_timeout,
            ) as resp,
        ):
            if resp.status == statuses.HTTP_204_NO_CONTENT:
                # All OK. Notification pushed.
                return

            if resp.status == statuses.HTTP_401_UNAUTHORIZED:
                APP_SESSIONS_STORAGE.remove_push_session(app_session_id)
                return

            if resp.status == statuses.HTTP_400_BAD_REQUEST:
                raise push_server_errors.BadRequestError(await resp.json())

            raise push_server_errors.UnexpectedServerResponseError(resp.status)
    except ClientError as e:
        raise push_server_errors.DomikaPushServerError(str(e)) from None


def _get_changed_attributes_from_event_data(event_data: EventStateChangedData) -> dict:
    old_state: CompressedState | dict = {}
    if event_data["old_state"]:
        old_state = event_data["old_state"].as_compressed_state

    new_state: CompressedState | dict = {}
    if event_data["new_state"]:
        new_state = event_data["new_state"].as_compressed_state

    # Make a flat dict from state data.
    old_attributes = flatten_json(old_state, exclude={"c", "lc", "lu"}) or {}
    new_attributes = flatten_json(new_state, exclude={"c", "lc", "lu"}) or {}

    # Calculate the changed attributes by subtracting old_state elements from new_state.
    return {k: v for k, v in new_attributes.items() if (k, v) not in old_attributes.items()}


def _fire_critical_sensor_notification(
        hass: HomeAssistant,
        event: Event[EventStateChangedData],
) -> None:
    # If entity id is a critical binary sensor.
    # Fetch state for all levels of critical binary sensors.
    sensors_data = critical_sensor_service.get(hass, NotificationType.ANY)
    # Fire the event for app.
    LOGGER.verbose("_fire_critical_sensor_notification started")
    hass.bus.async_fire(
        "domika_critical_sensors_changed",
        sensors_data.to_dict(),
        event.origin,
        event.context,
        event.time_fired.timestamp(),
    )


def _fire_event_to_app_session_ids(
        hass: HomeAssistant,
        event: Event[EventStateChangedData],
        event_id: str,
        entity_id: str,
        attributes: dict,
        app_session_ids: Iterable[str],
) -> None:
    LOGGER.verbose("_fire_event_to_app_session_ids started, app_session_ids: %s, event_id: %s, entity_id: %s, attributes: %s",
        app_session_ids,
        event_id,
        entity_id,
        attributes
    )
    dict_attributes = attributes
    dict_attributes["d.type"] = "state_changed"
    dict_attributes["event_id"] = event_id
    dict_attributes["entity_id"] = entity_id
    for app_session_id in app_session_ids:
        hass.bus.async_fire(
            f"domika_{app_session_id}",
            dict_attributes,
            event.origin,
            event.context,
            event.time_fired.timestamp(),
        )
        LOGGER.finest(
            "_fire_event_to_app_session_ids event fired: %s, dict_attributes: %s, "
            "event.origin: %s, event.context: %s, timestamp: %s",
            f"domika_{app_session_id}",
            dict_attributes,
            event.origin,
            event.context,
            event.time_fired.timestamp()
        )


async def _get_delay_by_entity_id(hass: HomeAssistant, entity_id: str) -> int:
    """Get push notifications delay by entity id."""
    state = hass.states.get(entity_id)
    if not state:
        return PUSH_DELAY_DEFAULT

    return PUSH_DELAY_FOR_DOMAIN.get(state.domain, PUSH_DELAY_DEFAULT)
