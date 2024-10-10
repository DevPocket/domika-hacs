"""Application key-value storage models."""

from dataclasses import dataclass

from mashumaro.mixins.json import DataClassJSONMixin
from sqlalchemy.orm import Mapped, mapped_column

from ..models import AsyncBase


class KeyValue(AsyncBase):
    """Application key-value storage."""

    __tablename__ = "key_value"

    user_id: Mapped[str] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]
    hash: Mapped[str]


@dataclass
class DomikaKeyValueBase(DataClassJSONMixin):
    """Base key-value model."""

    user_id: str
    key: str
    value: str
    hash: str


@dataclass
class DomikaKeyValueCreate(DomikaKeyValueBase):
    """Key-value create model."""


@dataclass
class DomikaKeyValueRead(DataClassJSONMixin):
    """Key-value read model."""

    user_id: str
    key: str
