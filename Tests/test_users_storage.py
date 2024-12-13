import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from custom_components.domika.storage.models import AppSession, Subscription
from custom_components.domika.storage.users_storage import UsersStorage, UsersStore


# Test models.py components
def test_app_session_init_from_dict():
    data = {
        "user_id": "user_456",
        "push_session_id": "push_789",
        "last_update": datetime.now(),
        "push_token_hash": "hash_abc"
    }
    session = AppSession.init_from_dict("123", data)
    assert session.id == "123"
    assert session.user_id == "user_456"
    assert session.push_session_id == "push_789"
    assert session.push_token_hash == "hash_abc"


def test_users_storage_update_and_get_data():
    users_storage = UsersStorage()

    # First record for user_123
    user_id_1 = "user_123"
    key_1 = "key_abc"
    value_1 = "value_xyz"
    value_hash_1 = "hash_123"
    with patch.object(users_storage, "_save_users_data"):
        users_storage.update_users_data(user_id_1, key_1, value_1, value_hash_1)

    # Second record for the same user_123
    key_2 = "key_def"
    value_2 = "value_uvw"
    value_hash_2 = "hash_456"
    with patch.object(users_storage, "_save_users_data"):
        users_storage.update_users_data(user_id_1, key_2, value_2, value_hash_2)

    # Third record for a different user_id: user_456
    user_id_2 = "user_456"
    value_3 = "value_abc"
    value_hash_3 = "hash_789"
    with patch.object(users_storage, "_save_users_data"):
        users_storage.update_users_data(user_id_2, key_1, value_3, value_hash_3)

    # Verify the records for user_123
    result_1 = users_storage.get_users_data(user_id_1, key_1)
    result_2 = users_storage.get_users_data(user_id_1, key_2)
    assert result_1 is not None
    assert result_1.value == value_1
    assert result_1.value_hash == value_hash_1
    assert result_2 is not None
    assert result_2.value == value_2
    assert result_2.value_hash == value_hash_2

    # Verify the record for user_456
    result_3 = users_storage.get_users_data(user_id_2, key_1)
    assert result_3 is not None
    assert result_3.value == value_1
    assert result_3.value_hash == value_hash_1

    result = users_storage.get_users_data(user_id_1, "non_existent_key")
    assert result is None

    result = users_storage.get_users_data("non_existent_user", key_1)
    assert result is None


def test_users_storage_get_users_data_not_found():
    users_storage = UsersStorage()
    result = users_storage.get_users_data("non_existent_user", "non_existent_key")
    assert result is None
