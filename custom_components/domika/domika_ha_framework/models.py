# vim: set fileencoding=utf-8
"""
Domika integration.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

from typing import Any, Literal

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

meta = MetaData(
    naming_convention={
        'ix': 'ix_%(column_0_label)s',
        'uq': 'uq_%(table_name)s_%(column_0_name)s',
        'ck': 'ck_%(table_name)s_`%(constraint_name)s`',
        'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
        'pk': 'pk_%(table_name)s',
    },
)


class AsyncBase(DeclarativeBase, AsyncAttrs):
    """Base async declarative type."""

    metadata = meta

    def dict(self) -> dict[str, Any]:
        """Return a dict representation of a model."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


NOT_SET = Literal['NOT_SET']
