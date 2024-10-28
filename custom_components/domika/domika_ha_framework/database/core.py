"""Database core."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import inspect

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    close_all_sessions,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry

from custom_components.domika.const import DATABASE_BUSY_TIMEOUT, LOGGER

from ..errors import DatabaseError


class NullSessionMaker:
    """
    Dummy sessionmaker.

    Need for not initialized AsyncSessionFactory.

    Raises:
        errors.DatabaseError: when try to access.
    """

    def __call__(self) -> "NullSessionMaker":
        """Just return self."""
        return self

    async def __aenter__(self):
        msg = "Database not initialized."
        raise DatabaseError(msg)

    async def __aexit__(self, _exc_type, _exc, _tb):  # noqa: ANN001
        pass


ENGINE: AsyncEngine | None = None

AsyncSessionFactory: NullSessionMaker | async_sessionmaker[AsyncSession] = (
    NullSessionMaker()
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(
    dbapi_connection: DBAPIConnection,
    connection_record: ConnectionPoolEntry,
):
    """
    Called when a new connection made for a pool.

    Args:
        dbapi_connection: a DBAPI connection. The ConnectionPoolEntry.dbapi_connection
            attribute.
        connection_record: the ConnectionPoolEntry managing the DBAPI connection.
    """
    del connection_record  # Unused
    cursor = dbapi_connection.cursor()
    cursor.execute(
        f"PRAGMA busy_timeout = {DATABASE_BUSY_TIMEOUT.total_seconds() * 1000};",  # ms
    )
    cursor.close()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Return async database session."""
    async with AsyncSessionFactory() as session:
        frame_info = inspect.stack()[2]
        LOGGER.debug(
            "Create db session: file: %s function: %s line: %d",
            frame_info.filename,
            frame_info.function,
            frame_info.lineno,
        )
        yield session
        LOGGER.debug(
            "Destroy db session: file: %s function: %s line: %d",
            frame_info.filename,
            frame_info.function,
            frame_info.lineno,
        )


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
        AsyncSessionFactory = NullSessionMaker()
