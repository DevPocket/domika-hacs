# vim: set fileencoding=utf-8
"""
Application dashboard.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

import sqlalchemy
import sqlalchemy.dialects.sqlite as sqlite_dialect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import DatabaseError
from .models import Dashboard, DomikaDashboardCreate, DomikaDashoardUpdate


async def get(db_session: AsyncSession, user_id: str) -> Dashboard | None:
    """
    Get dashboard by user id.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    try:
        stmt = sqlalchemy.select(Dashboard).where(Dashboard.user_id == user_id)
        return await db_session.scalar(stmt)
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def create_or_update(
    db_session: AsyncSession,
    dashboard_in: DomikaDashboardCreate,
    *,
    commit: bool = True,
) -> Dashboard | None:
    """
    Create or update dashboard.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlite_dialect.insert(Dashboard)
    stmt = stmt.values(**dashboard_in.to_dict())
    stmt = stmt.on_conflict_do_update(
        index_elements=[Dashboard.user_id],
        set_={
            "dashboards": stmt.excluded.dashboards,
            "hash": stmt.excluded.hash,
        },
    )
    stmt = stmt.returning(Dashboard)

    try:
        result = await db_session.scalar(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e

    return result


async def update(
    db_session: AsyncSession,
    dashboard: Dashboard,
    dashboard_in: DomikaDashoardUpdate,
    *,
    commit: bool = True,
):
    """
    Update dashboard.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    dashboard_attrs = dashboard.dict()
    update_data = dashboard_in.to_dict()
    for attr in dashboard_attrs:
        if attr in update_data:
            setattr(dashboard, attr, update_data[attr])

    try:
        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e


async def delete(
    db_session: AsyncSession,
    user_id: str,
    *,
    commit: bool = True,
):
    """
    Delete dashboard.

    Raise:
        errors.DatabaseError: in case when database operation can't be performed.
    """
    stmt = sqlalchemy.delete(Dashboard).where(Dashboard.user_id == user_id)

    try:
        await db_session.execute(stmt)

        if commit:
            await db_session.commit()
    except SQLAlchemyError as e:
        raise DatabaseError(str(e)) from e
