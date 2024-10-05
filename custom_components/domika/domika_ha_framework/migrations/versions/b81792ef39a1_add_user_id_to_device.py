"""
Add user_id to device.

Revision ID: b81792ef39a1
Revises: d9d8c5c24b47
Create Date: 2024-05-28 17:25:17.648560
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b81792ef39a1"
down_revision: Union[str, None] = "d9d8c5c24b47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade step."""
    with op.batch_alter_table("devices", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("user_id", sa.String(), nullable=False, server_default=""),
            insert_after="app_session_id",
        )

    with op.batch_alter_table("devices") as batch_op:
        batch_op.alter_column("user_id", server_default=None)


def downgrade() -> None:
    """Downgrade step."""
    with op.batch_alter_table("devices") as batch_op:
        batch_op.drop_column("user_id")
