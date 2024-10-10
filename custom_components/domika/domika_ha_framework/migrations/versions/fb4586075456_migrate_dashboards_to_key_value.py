"""
migrate dashboards to key-value.

Revision ID: fb4586075456
Revises: 9a0623c36ae4
Create Date: 2024-10-06 20:42:33.062459
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "fb4586075456"
down_revision: str | None = "9a0623c36ae4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade step."""
    # Migrate existing data from dashboards table to key-value.
    key_value_table = sa.sql.table(
        "key_value",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("hash", sa.String(), nullable=False),
    )

    conn = op.get_bind()
    # Remove existing dashboards data from key_value table.
    conn.execute(sa.text("DELETE FROM key_value WHERE key='app.dashboards'"))

    res = conn.execute(sa.text("SELECT user_id, dashboards, hash FROM dashboards"))
    results = res.fetchall()

    # Prepare an old_info object to insert into the new key_value table.
    old_info = [
        {"user_id": r[0], "key": "app.dashboards", "value": r[1], "hash": r[2]}
        for r in results
    ]

    # Insert old_info into new key_value table.
    op.bulk_insert(key_value_table, old_info)

    # Remove dashboards table.
    op.drop_table("dashboards")


def downgrade() -> None:
    """Downgrade step."""
    dashboards_table = op.create_table(
        "dashboards",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("dashboards", sa.String(), nullable=False),
        sa.Column("hash", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_dashboards")),
    )

    conn = op.get_bind()
    res = conn.execute(
        sa.text(
            "SELECT user_id, value, hash FROM key_value WHERE key='app.dashboards'",
        ),
    )
    results = res.fetchall()

    # Prepare an old_info object to insert into the new dashboards_table.
    old_info = [{"user_id": r[0], "dashboards": r[1], "hash": r[2]} for r in results]

    # Insert old_info into dashboards_table.
    op.bulk_insert(dashboards_table, old_info)

    # Remove existing dashboards data from key_value table.
    conn.execute(sa.text("DELETE FROM key_value WHERE key='app.dashboards'"))
