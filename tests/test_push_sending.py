"""A push failure for one app session must not stop pushes to the others."""

from unittest.mock import AsyncMock, Mock, patch

from custom_components.domika import push_server_errors
from custom_components.domika.ha_event import flow
from custom_components.domika.push_data_storage.models import PushData
from custom_components.domika.storage.models import Sessions


def _state_changed_event() -> Mock:
    new_state = Mock()
    new_state.as_compressed_state = {"s": "on", "a": {"device_class": "smoke"}}
    event = Mock()
    event.data = {"entity_id": "binary_sensor.smoke", "old_state": None, "new_state": new_state}
    event.time_fired_timestamp = 1
    return event


async def test_critical_push_reaches_every_session_when_one_fails(hass):
    send = AsyncMock(side_effect=[push_server_errors.UnexpectedServerResponseError(500), TimeoutError(), None])
    sessions = [Sessions("a", "pa"), Sessions("b", "pb"), Sessions("c", "pc")]

    with (
        patch.object(flow, "_send_push_data", send),
        patch.object(flow, "async_get_clientsession"),
        patch.object(flow, "async_get_translations", AsyncMock(return_value={})),
        patch.object(flow.critical_sensor_service, "check_notification_type", return_value=False),
        patch.object(flow.critical_sensor_service, "critical_push_needed", return_value=True),
        patch.object(flow, "_get_critical_alert_payload", return_value={}),
        patch.object(flow.APP_SESSIONS_STORAGE, "get_app_sessions_with_push_session", return_value=sessions),
        patch.object(flow.PUSHDATA_STORAGE, "process_entity_changes"),
    ):
        await flow.register_event(hass, _state_changed_event())

    assert [c.args[3] for c in send.await_args_list] == ["a", "b", "c"]


async def test_process_push_data_sends_to_others_and_keeps_failed_data(hass, push_data):
    push_data.insert(PushData("e1", "a", "pa", "light.x", "s", "on", "c", 1, 0))
    push_data.insert(PushData("e2", "b", "pb", "light.x", "s", "on", "c", 1, 0))

    async def send(_session, _url, _timeout, app_session_id, *_args, **_kwargs):
        if app_session_id == "a":
            raise push_server_errors.BadRequestError({"detail": "bad"})

    with (
        patch.object(flow, "_send_push_data", AsyncMock(side_effect=send)) as send_mock,
        patch.object(flow, "async_get_clientsession"),
    ):
        await flow.process_push_data(hass)

    assert sorted(c.args[3] for c in send_mock.await_args_list) == ["a", "b"]
    assert [key[0] for key in push_data.storage] == ["a"]
