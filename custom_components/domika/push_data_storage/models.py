"""Push data models."""
from dataclasses import dataclass


@dataclass
class PushData:
    event_id: str
    app_session_id: str
    entity_id: str
    attribute: str
    value: str
    context_id: str
    timestamp: int
    delay: int
