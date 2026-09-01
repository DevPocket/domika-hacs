"""Critical sensor models."""

from dataclasses import dataclass, field

from mashumaro.mixins.json import DataClassJSONMixin

from .enums import NotificationType


@dataclass
class DomikaNotificationSensor(DataClassJSONMixin):
    """Notification sensor data."""

    entity_id: str
    type: NotificationType = field(metadata={"serialize": lambda v: v.to_string()})
    name: str
    device_class: str
    state: str
    timestamp: int
    # Device info for grouping sensors in the app; absent when the entity has no device.
    device_id: str | None = None
    device_name: str | None = None
    device_type: str | None = None


@dataclass
class DomikaNotificationSensorsRead(DataClassJSONMixin):
    """Notification sensors read model."""

    sensors: list[DomikaNotificationSensor]
    sensors_on: list[str]
