"""Database core."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    close_all_sessions,
    create_async_engine,
)

from custom_components.domika.const import LOGGER

from ..errors import DatabaseError


class NullSessionMaker:
    """
    Dummy sessionmaker.

    Need for not initialized AsyncSessionFactory.

    Raises:
        errors.DatabaseError: when try to access.
    """

    async def __aenter__(self):
        msg = "Database not initialized."
        raise DatabaseError(msg)

    async def __aexit__(self, _exc_type, _exc, _tb):  # noqa: ANN001
        pass


ENGINE: AsyncEngine | None = None

AsyncSessionFactory = NullSessionMaker


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Return async database session."""
    async with AsyncSessionFactory() as session:
        yield session


async def init_db(db_url: str):
    """
    Initialize database.

    If previously initialized - close old database.

    Raises:
        errors.DatabaseError: if database can't be initialized.
    """
    global ENGINE, AsyncSessionFactory  # noqa: PLW0603

    if ENGINE:
        await close_db()

    try:
        ENGINE = create_async_engine(db_url, echo=False)
        AsyncSessionFactory = async_sessionmaker(ENGINE, expire_on_commit=False)
    except (OSError, SQLAlchemyError) as e:
        raise DatabaseError(e) from e

    LOGGER.debug('Database "%s" initialized.', ENGINE.url)


async def close_db():
    """Close all sessions and dispose database connection pool."""
    global ENGINE, AsyncSessionFactory  # noqa: PLW0603
    if ENGINE:
        await close_all_sessions()
        await ENGINE.dispose()

        LOGGER.debug('Database "%s" closed.', ENGINE.url)

        ENGINE = None
        AsyncSessionFactory = NullSessionMaker
