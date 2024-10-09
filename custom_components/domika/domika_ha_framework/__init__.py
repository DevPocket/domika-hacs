# vim: set fileencoding=utf-8
"""
domika-ha-framework.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

from . import config, push_data
from .database import core as database_core
from .database import manage as database_manage


async def init(cfg: config.Config):
    """
    Initialize library with config.

    Perform migration if needed.

    Raise:
        DatabaseError, if can't be initialized.
    """
    config.CONFIG = cfg
    await database_core.init_db()
    await database_manage.migrate()
    push_data.start_push_data_processor()


async def dispose():
    """Clean opened resources and close database connections."""
    await push_data.stop_push_data_processor()
    await database_core.close_db()
