"""Push tokens, purchase ids and verification keys must not reach the log."""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.domika import push_server_errors
from custom_components.domika.sessions import router as sessions_router

from .conftest import add_session, make_connection

SECRETS = ("PUSH-TOKEN-SECRET", "TRANSACTION-SECRET", "VERIFICATION-SECRET")


@pytest.fixture
def debug_log(caplog):
    caplog.set_level(logging.DEBUG, logger="custom_components.domika")
    return caplog


def _assert_no_secrets(caplog) -> None:
    for secret in SECRETS:
        assert secret not in caplog.text


@pytest.mark.parametrize(
    "error",
    [ValueError("missing"), push_server_errors.DomikaPushServerError("down"), RuntimeError("boom"), None],
)
async def test_create_push_session_logs_no_secrets(hass, debug_log, error):
    flow = AsyncMock(side_effect=error)
    with (
        patch.object(sessions_router.sessions_flow, "create_push_session", flow),
        patch.object(sessions_router, "async_get_clientsession"),
    ):
        await sessions_router._create_push_session(
            hass, "TRANSACTION-SECRET", "ios", "sandbox", "sandbox", "PUSH-TOKEN-SECRET", "s",
        )

    assert debug_log.records
    _assert_no_secrets(debug_log)


@pytest.mark.parametrize(
    "error",
    [
        ValueError("missing"),
        push_server_errors.BadRequestError({"detail": "bad"}),
        push_server_errors.DomikaPushServerError("down"),
        RuntimeError("boom"),
        None,
    ],
)
async def test_verify_push_session_logs_no_secrets(hass, debug_log, error):
    flow = AsyncMock(side_effect=error, return_value="push_session")
    with (
        patch.object(sessions_router.sessions_flow, "verify_push_session", flow),
        patch.object(sessions_router, "async_get_clientsession"),
    ):
        await sessions_router._verify_push_session(hass, "s", "VERIFICATION-SECRET", "hash")

    assert debug_log.records
    _assert_no_secrets(debug_log)


async def test_push_session_commands_log_no_secrets(hass, app_sessions, debug_log):
    add_session(app_sessions, "s", "owner")
    messages = [
        (
            sessions_router.websocket_domika_update_push_session,
            {
                "original_transaction_id": "TRANSACTION-SECRET",
                "push_token_hex": "PUSH-TOKEN-SECRET",
                "platform": "ios",
                "environment": "sandbox",
            },
        ),
        (
            sessions_router.websocket_domika_update_push_session_v2,
            {
                "original_transaction_id": "TRANSACTION-SECRET",
                "push_token_hex": "PUSH-TOKEN-SECRET",
                "platform": "ios",
                "push_environment": "sandbox",
                "transaction_environment": "sandbox",
            },
        ),
        (
            sessions_router.websocket_domika_verify_push_session,
            {"verification_key": "VERIFICATION-SECRET", "push_token_hash": "hash"},
        ),
    ]
    for handler, extra in messages:
        await handler.__wrapped__(hass, make_connection("owner"), {"id": 1, "app_session_id": "s", **extra})

    assert debug_log.records
    _assert_no_secrets(debug_log)
