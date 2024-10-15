"""Database management functions."""

import asyncio
import os
from pathlib import Path

import alembic.command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from custom_components.domika.const import LOGGER

ALEMBIC_INI_PATH = Path(Path(__file__).parent) / ".." / "alembic.ini"


def _run_upgrade(connection: Connection, cfg: AlembicConfig):
    cfg.attributes["connection"] = connection
    alembic.command.upgrade(cfg, "head")


async def _migrate(db_url: str):
    alembic_config = AlembicConfig(ALEMBIC_INI_PATH)
    alembic_config.attributes["configure_loggers"] = False
    alembic_config.attributes["DOMIKA_DB_URL"] = db_url
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_run_upgrade, alembic_config)
    await engine.dispose()


async def migrate(db_url: str):
    """
    Perform database migration.

    All this strange stuff is made only for one reason - avoid HA warning about
    synchronous calls.
    Alembic developers do not plan to do true async migrations.
    """
    # Clear DOMIKA_DB_URL environment variable. It should be used only with alembic
    # direct call.
    os.environ["DOMIKA_DB_URL"] = ""
    await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: asyncio.run(_migrate(db_url)),
    )
    LOGGER.debug("Database migration successful")
