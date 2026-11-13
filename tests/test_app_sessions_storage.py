"""App sessions storage."""

from datetime import datetime, timedelta

from .conftest import add_session


def test_delete_inactive_removes_every_stale_session(app_sessions):
    stale = int((datetime.now() - timedelta(days=40)).timestamp())
    add_session(app_sessions, "old1", "u1", last_update=stale)
    add_session(app_sessions, "old2", "u1", last_update=stale)
    add_session(app_sessions, "fresh", "u1")

    app_sessions.delete_inactive(timedelta(days=30))

    assert app_sessions.get_all_app_sessions() == ["fresh"]


def test_remove_all_with_push_token_hash_removes_every_match(app_sessions):
    add_session(app_sessions, "a", "u1", push_token_hash="h")
    add_session(app_sessions, "b", "u2", push_token_hash="h")
    add_session(app_sessions, "keep", "u1", push_token_hash="h")
    add_session(app_sessions, "other", "u1", push_token_hash="x")

    app_sessions.remove_all_with_push_token_hash("h", "keep")

    assert sorted(app_sessions.get_all_app_sessions()) == ["keep", "other"]
