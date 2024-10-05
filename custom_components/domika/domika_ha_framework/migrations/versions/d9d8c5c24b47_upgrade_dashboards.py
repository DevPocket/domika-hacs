"""
Upgrade dashboards.

Revision ID: d9d8c5c24b47
Revises: 9291d34e8062
Create Date: 2024-05-28 16:24:17.109626
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9d8c5c24b47"
down_revision: Union[str, None] = "9291d34e8062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade step."""
    with op.batch_alter_table("dashboards") as batch_op:
        batch_op.alter_column("dashboard", new_column_name="dashboards")
        batch_op.add_column(sa.Column("hash", sa.String(), nullable=False, server_default=""))

    with op.batch_alter_table("dashboards") as batch_op:
        batch_op.alter_column("hash", server_default=None)


def downgrade() -> None:
    """Downgrade step."""
    with op.batch_alter_table("dashboards") as batch_op:
        batch_op.alter_column("dashboards", new_column_name="dashboard")
        batch_op.drop_column("hash")
