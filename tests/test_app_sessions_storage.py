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


def test_belongs_to_other_user(app_sessions):
    add_session(app_sessions, "s", "u1")

    assert not app_sessions.belongs_to_other_user("s", "u1")
    assert app_sessions.belongs_to_other_user("s", "u2")
    assert not app_sessions.belongs_to_other_user("missing", "u2")


def test_shares_device_with_user(app_sessions):
    add_session(app_sessions, "theirs", "u2", push_token_hash="h")
    add_session(app_sessions, "mine", "u1", push_token_hash="h")
    add_session(app_sessions, "no_hash", "u2")

    assert app_sessions.shares_device_with_user("theirs", "u1")
    assert not app_sessions.shares_device_with_user("theirs", "u3")
    assert not app_sessions.shares_device_with_user("no_hash", "u1")
