# vim: set fileencoding=utf-8
"""
Push data.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from mashumaro import pass_through
from mashumaro.config import BaseConfig
from mashumaro.mixins.json import DataClassJSONMixin
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from ..models import AsyncBase


class PushData(AsyncBase):
    """Data to be pushed."""

    __tablename__ = "push_data"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    app_session_id: Mapped[str] = mapped_column(
        ForeignKey("devices.app_session_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    entity_id: Mapped[str] = mapped_column(primary_key=True)
    attribute: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]
    context_id: Mapped[str]
    timestamp: Mapped[int] = mapped_column(server_default=func.datetime("now"))
    delay: Mapped[int]


class _Event(AsyncBase):
    """HomeAssistant temporary event."""

    __tablename__ = "events"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    entity_id: Mapped[str] = mapped_column(primary_key=True)
    attribute: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]
    context_id: Mapped[str]
    timestamp: Mapped[int] = mapped_column(server_default=func.datetime("now"))
    delay: Mapped[int]


@dataclass
class DomikaPushDataBase(DataClassJSONMixin):
    """Base event model."""

    event_id: uuid.UUID = field(
        metadata={
            "serialization_strategy": pass_through,
        },
    )
    entity_id: str
    attribute: str
    value: str
    context_id: str
    timestamp: int
    delay: int


@dataclass
class DomikaPushDataCreate(DomikaPushDataBase):
    """Push data create model."""


@dataclass
class DomikaPushDataUpdate(DataClassJSONMixin):
    """Push data update model."""

    value: Optional[str]
    timestamp: Optional[int]

    class Config(BaseConfig):
        """Mashumaro config."""

        omit_default = True


@dataclass
class DomikaPushedEvents(DataClassJSONMixin):
    """Pushed events' config."""

    push_session_id: uuid.UUID = field(
        metadata={
            "serialization_strategy": pass_through,
        },
    )
    events: dict[str, dict[str, Any]]
