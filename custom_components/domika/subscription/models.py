"""User event subscriptions models."""

from dataclasses import dataclass
from mashumaro.mixins.json import DataClassJSONMixin

_EntityToAttribute = dict[str, set[str]]
SubscriptionMap = dict[str, _EntityToAttribute]


@dataclass
class Subscription(DataClassJSONMixin):
    """Event subscriptions."""
    app_session_id: str
    entity_id: str
    attribute: str
    need_push: str
