"""User event subscriptions models."""

from dataclasses import dataclass, field

from mashumaro import pass_through
from mashumaro.mixins.json import DataClassJSONMixin
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from ..models import AsyncBase

_EntityToAttribute = dict[str, set[str]]
SubscriptionMap = dict[str, _EntityToAttribute]


class Subscription(AsyncBase):
    """Event subscriptions."""

    __tablename__ = "subscriptions"

    app_session_id: Mapped[str] = mapped_column(
        ForeignKey("devices.app_session_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    entity_id: Mapped[str] = mapped_column(primary_key=True)
    attribute: Mapped[str] = mapped_column(primary_key=True)
    need_push: Mapped[bool]


@dataclass
class DomikaSubscriptionBase(DataClassJSONMixin):
    """Base subscription model."""

    app_session_id: str = field(
        metadata={
            "serialization_strategy": pass_through,
        },
    )
    entity_id: str
    attribute: str
    need_push: bool


@dataclass
class DomikaSubscriptionCreate(DomikaSubscriptionBase):
    """Subscription create model."""


@dataclass
class DomikaSubscriptionRead(DomikaSubscriptionBase):
    """Subscription read model."""


@dataclass
class DomikaSubscriptionUpdate(DataClassJSONMixin):
    """Subscription update model."""

    need_push: bool
