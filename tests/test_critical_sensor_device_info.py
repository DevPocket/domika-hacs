"""Tests for device info in critical sensor data (used by the app for smiley grouping)."""

from unittest.mock import Mock, patch

from custom_components.domika.critical_sensor import service
from custom_components.domika.critical_sensor.enums import NotificationType
from custom_components.domika.critical_sensor.models import DomikaNotificationSensor


def test_device_type_prefers_safety_classes():
    assert service.device_type(["battery", "smoke"]) == "smoke"
    assert service.device_type(["battery", "tamper", "gas"]) == "gas"
    assert service.device_type(["battery", "cold"]) == "cold"


def test_device_type_falls_back_to_first_class():
    assert service.device_type(["battery"]) == "battery"
    assert service.device_type(["something_else", "another"]) == "something_else"
    assert service.device_type([]) is None


def test_notification_sensor_serializes_device_info():
    sensor = DomikaNotificationSensor(
        entity_id="binary_sensor.smoke",
        type=NotificationType.CRITICAL,
        name="Smoke",
        device_class="smoke",
        state="on",
        timestamp=1,
        device_id="device1",
        device_name="Smoke Detector",
        device_type="smoke",
    )
    data = sensor.to_dict()
    assert data["device_id"] == "device1"
    assert data["device_name"] == "Smoke Detector"
    assert data["device_type"] == "smoke"


def test_notification_sensor_device_info_defaults_to_none():
    sensor = DomikaNotificationSensor(
        entity_id="binary_sensor.smoke",
        type=NotificationType.CRITICAL,
        name="Smoke",
        device_class="smoke",
        state="on",
        timestamp=1,
    )
    data = sensor.to_dict()
    assert data["device_id"] is None
    assert data["device_name"] is None
    assert data["device_type"] is None


def _state(entity_id: str, device_class: str, state: str = "on") -> Mock:
    sensor_state = Mock()
    sensor_state.name = f"Name of {entity_id}"
    sensor_state.state = state
    sensor_state.attributes = {"device_class": device_class}
    sensor_state.last_updated_timestamp = 1.0
    sensor_state.last_changed_timestamp = 1.0
    return sensor_state


def _registry_entry(device_id: str | None) -> Mock:
    entry = Mock()
    entry.hidden_by = None
    entry.disabled_by = None
    entry.device_id = device_id
    return entry


def test_get_fills_device_info_from_device_registry():
    states = {
        "binary_sensor.smoke": _state("binary_sensor.smoke", "smoke"),
        "binary_sensor.battery": _state("binary_sensor.battery", "battery", state="off"),
        "binary_sensor.lonely": _state("binary_sensor.lonely", "gas"),
    }
    registry_entries = {
        "binary_sensor.smoke": _registry_entry("device1"),
        "binary_sensor.battery": _registry_entry("device1"),
        "binary_sensor.lonely": _registry_entry(None),
    }
    device = Mock()
    device.id = "device1"
    device.name = "Smoke Detector"
    device.name_by_user = "Kitchen Detector"

    hass = Mock()
    hass.data = {}
    hass.states.async_entity_ids = Mock(return_value=list(states))
    hass.states.get = Mock(side_effect=states.get)

    entity_registry = Mock()
    entity_registry.entities = registry_entries
    device_registry = Mock()
    device_registry.async_get = Mock(side_effect={"device1": device}.get)

    with (
        patch.object(service.er, "async_get", return_value=entity_registry),
        patch.object(service.dr, "async_get", return_value=device_registry),
    ):
        result = service.get(hass, NotificationType.ANY)

    sensors = {sensor.entity_id: sensor for sensor in result.sensors}
    assert set(sensors) == set(states)

    smoke = sensors["binary_sensor.smoke"]
    assert smoke.device_id == "device1"
    assert smoke.device_name == "Kitchen Detector"  # name_by_user wins over name
    assert smoke.device_type == "smoke"  # smoke beats battery for the shared device

    battery = sensors["binary_sensor.battery"]
    assert battery.device_id == "device1"
    assert battery.device_type == "smoke"

    lonely = sensors["binary_sensor.lonely"]
    assert lonely.device_id is None
    assert lonely.device_name is None
    assert lonely.device_type is None
