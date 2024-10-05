# vim: set fileencoding=utf-8
"""
Database core.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

import asyncio
import os
from pathlib import Path

import alembic.command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from .. import config, logger

ALEMBIC_INI_PATH = Path(Path(__file__).parent) / ".." / "alembic.ini"


def _run_upgrade(connection: Connection, cfg: AlembicConfig):
    cfg.attributes["connection"] = connection
    cfg.attributes["configure_loggers"] = False
    alembic.command.upgrade(cfg, "head")


async def _migrate():
    alembic_config = AlembicConfig(ALEMBIC_INI_PATH)
    engine = create_async_engine(config.CONFIG.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_run_upgrade, alembic_config)


async def migrate():
    """
    Perform database migration.

    All this strange stuff is made only for one reason - avoid HA warning about synchronous calls.
    Alembic developers do not plan to do true async migrations.
    """
    # Clear DOMIKA_DB_URL environment variable. It should be used only with alembic direct call.
    os.environ["DOMIKA_DB_URL"] = ""
    await asyncio.get_event_loop().run_in_executor(None, lambda: asyncio.run(_migrate()))
    logger.logger.debug("Database migration successful")
