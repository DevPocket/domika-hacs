"""Push data flow functions."""

import json

import aiohttp
from aiohttp import ClientTimeout
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession

from custom_components.domika.const import LOGGER

from .. import push_server_errors, statuses
from ..device import service as device_service
from ..device.models import Device, DomikaDeviceUpdate
from . import confirmed_events_queue, events_queue
from .models import DomikaPushDataCreate, DomikaPushedEvents, PushData
from .service import decrease_delay_all, delete_by_app_session_id
from ...storage.storage import STORAGE


async def confirm_event(event_ids: list[str]) -> None:
    """
    Confirm that event is fully processed by the application.

    Args:
        event_ids: list event id's that was confirmed by the application.
    """
    for event in event_ids:
        await confirmed_events_queue.put(event)


async def register_event(
    http_session: aiohttp.ClientSession,
    push_server_url: str,
    push_server_timeout: ClientTimeout,
    *,
    push_data: list[DomikaPushDataCreate],
    critical_push_needed: bool,
    critical_alert_payload: dict,
) -> list[DomikaPushedEvents]:
    """
    Register new push data, and send critical push if needed.

    All push data items must belong to the same entity and share same context.

    Args:
        http_session: aiohttp session.
        push_server_url: domika push server url.
        push_server_timeout: domika push server response timeout.
        push_data: list of push data entities.
        critical_push_needed: critical push flag.
        critical_alert_payload: payload in case we need to send a critical push.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
        push_server_errors.DomikaPushServerError: in case of internal aiohttp error.
        push_server_errors.BadRequestError: if push server response with bad request.
        push_server_errors.UnexpectedServerResponseError: if push server response with
            unexpected status.
    """
    result: list[DomikaPushedEvents] = []
    if not push_data:
        return result

    for event in push_data:
        await events_queue.put(event)

    if critical_push_needed:
        verified_devices = await device_service.get_all_with_push_session_id()

        for device in verified_devices:
            if not device.push_session_id:
                continue

            await _send_push_data(
                None,
                http_session,
                push_server_url,
                push_server_timeout,
                device.app_session_id,
                device.push_session_id,
                critical_alert_payload,
                critical=True,
            )

    return result


async def push_registered_events(
    db_session: AsyncSession,
    http_session: aiohttp.ClientSession,
    push_server_url: str,
    push_server_timeout: ClientTimeout,
) -> list[DomikaPushedEvents]:
    """
    Push registered events with delay = 0 to the push server.

    Select registered events with delay = 0, add events with delay > 0 for the same
    app_session_ids, create formatted push data, send it to the push server api,
    delete all registered events for involved app sessions.

    Args:
        db_session: sqlalchemy session.
        http_session: aiohttp session.
        push_server_url: domika push server url.
        push_server_timeout: domika push server response timeout.

    Raises:
        errors.DatabaseError: in case when database operation can't be performed.
        push_server_errors.DomikaPushServerError: in case of internal aiohttp error.
        push_server_errors.BadRequestError: if push server response with bad request.
        push_server_errors.UnexpectedServerResponseError: if push server response with
            unexpected status.
    """
    LOGGER.debug("Push_registered_events started.")

    result: list[DomikaPushedEvents] = []
    await decrease_delay_all(db_session)

    stmt = sqlalchemy.select(PushData, Device.push_session_id)
    stmt = stmt.join(Device, PushData.app_session_id == Device.app_session_id)
    stmt = stmt.where(Device.push_session_id.is_not(None))
    stmt = stmt.order_by(
        Device.push_session_id,
        PushData.entity_id,
    )
    push_data_records = (await db_session.execute(stmt)).all()

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
        if current_app_session_id != push_data_record[0].app_session_id:
            if (
                found_delay_zero
                and events_dict
                and current_push_session_id
                and current_app_session_id
            ):
                result.append(DomikaPushedEvents(current_push_session_id, events_dict))
                await _send_push_data(
                    db_session,
                    http_session,
                    push_server_url,
                    push_server_timeout,
                    current_app_session_id,
                    current_push_session_id,
                    events_dict,
                )
                app_sessions_ids_to_delete_list.append(current_app_session_id)
            current_push_session_id = push_data_record[1]
            current_app_session_id = push_data_record[0].app_session_id
            current_entity_id = None
            events_dict = {}
            found_delay_zero = False
        if current_entity_id != push_data_record[0].entity_id:
            entity = {}
            events_dict[push_data_record[0].entity_id] = entity
            current_entity_id = push_data_record[0].entity_id
        entity[push_data_record[0].attribute] = {
            "v": push_data_record[0].value,
            "t": push_data_record[0].timestamp,
        }
        found_delay_zero = found_delay_zero or (push_data_record[0].delay == 0)

    if (
        found_delay_zero
        and events_dict
        and current_push_session_id
        and current_app_session_id
    ):
        result.append(DomikaPushedEvents(current_push_session_id, events_dict))
        await _send_push_data(
            db_session,
            http_session,
            push_server_url,
            push_server_timeout,
            current_app_session_id,
            current_push_session_id,
            events_dict,
        )
        app_sessions_ids_to_delete_list.append(current_app_session_id)

    await delete_by_app_session_id(db_session, app_sessions_ids_to_delete_list)

    return result


async def _clear_push_session_id(
    db_session: AsyncSession,
    app_session_id: str,
    push_session_id: str,
) -> None:
    # Push session id not found on push server.
    # Remove push session id for device.
    device = STORAGE.get_app_session(app_session_id)
    if device:
        LOGGER.debug(
            'The server rejected push session id "%s"',
            push_session_id,
        )
        await device_service.update(
            db_session,
            device,
            DomikaDeviceUpdate(push_session_id=None),
        )
        LOGGER.debug(
            'Push session "%s" for app session "%s" successfully removed',
            push_session_id,
            app_session_id,
        )


async def _send_push_data(
    db_session: AsyncSession | None,
    http_session: aiohttp.ClientSession,
    push_server_url: str,
    push_server_timeout: ClientTimeout,
    app_session_id: str,
    push_session_id: str,
    critical_alert_payload: dict,
    *,
    critical: bool = False,
) -> None:
    LOGGER.debug(
        "Push events %sto %s. %s",
        "(critical) " if critical else "",
        push_session_id,
        critical_alert_payload,
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
                json={"data": json.dumps(critical_alert_payload)},
                timeout=push_server_timeout,
            ) as resp,
        ):
            if resp.status == statuses.HTTP_204_NO_CONTENT:
                # All OK. Notification pushed.
                return

            if resp.status == statuses.HTTP_401_UNAUTHORIZED:
                if db_session is None:
                    # Create database session implicitly.
                    async with database_core.get_session() as db_session_:
                        await _clear_push_session_id(
                            db_session_,
                            app_session_id,
                            push_session_id,
                        )
                    return

                await _clear_push_session_id(
                    db_session,
                    app_session_id,
                    push_session_id,
                )
                return

            if resp.status == statuses.HTTP_400_BAD_REQUEST:
                raise push_server_errors.BadRequestError(await resp.json())

            raise push_server_errors.UnexpectedServerResponseError(resp.status)
    except aiohttp.ClientError as e:
        raise push_server_errors.DomikaPushServerError(str(e)) from None
