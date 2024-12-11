"""Application key-value storage models."""

from dataclasses import dataclass

from mashumaro.mixins.json import DataClassJSONMixin
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from typing import Any

meta = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_`%(constraint_name)s`",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    },
)
class AsyncBase(DeclarativeBase, AsyncAttrs):
    """Base async declarative type."""

    metadata = meta

    def dict(self) -> dict[str, Any]:
        """Return a dict representation of a model."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

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
