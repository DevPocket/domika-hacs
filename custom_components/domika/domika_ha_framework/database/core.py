# vim: set fileencoding=utf-8
"""
Database core.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    close_all_sessions,
    create_async_engine,
)

from .. import config, logger
from ..errors import DatabaseError


class NullSessionMaker:
    """
    Dummy sessionmaker.

    Need for not initialized AsyncSessionFactory.

    Raise:
        errors.DatabaseError: when try to access.
    """

    async def __aenter__(self):
        msg = "Database not initialized."
        raise DatabaseError(msg)

    async def __aexit__(self, _exc_type, _exc, _tb):  # noqa
        pass


ENGINE: Optional[AsyncEngine] = None

AsyncSessionFactory = NullSessionMaker


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Return async database session."""
    async with AsyncSessionFactory() as session:
        yield session


async def init_db():
    """
    Initialize database.

    If previously initialized - close old database.

    Raise:
        errors.DatabaseError: if database can't be initialized.
    """
    global ENGINE, AsyncSessionFactory  # noqa: PLW0603

    if ENGINE:
        await close_db()

    try:
        ENGINE = create_async_engine(config.CONFIG.database_url, echo=False)
        AsyncSessionFactory = async_sessionmaker(ENGINE, expire_on_commit=False)
    except (OSError, SQLAlchemyError) as e:
        raise DatabaseError(e) from e

    logger.logger.debug('Database "%s" initialized.', ENGINE.url)


async def close_db():
    """Close all sessions and dispose database connection pool."""
    global ENGINE, AsyncSessionFactory  # noqa: PLW0603
    if ENGINE:
        await close_all_sessions()
        await ENGINE.dispose()

        logger.logger.debug('Database "%s" closed.', ENGINE.url)

        ENGINE = None
        AsyncSessionFactory = NullSessionMaker
