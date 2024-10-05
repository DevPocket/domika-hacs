"""
add push_token hash to devices.

Revision ID: 939806f0fa92
Revises: 3e2eb2f9d056
Create Date: 2024-07-15 17:01:01.856087
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "939806f0fa92"
down_revision: Union[str, None] = "3e2eb2f9d056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade step."""
    with op.batch_alter_table("devices", recreate="never") as batch_op:
        batch_op.drop_column("push_token")
        batch_op.drop_column("platform")
        batch_op.drop_column("environment")
        batch_op.add_column(
            sa.Column("push_token_hash", sa.String(), nullable=False, server_default=""),
        )


def downgrade() -> None:
    """Downgrade step."""
    with op.batch_alter_table("devices", recreate="never") as batch_op:
        batch_op.drop_column("push_token_hash")
        batch_op.add_column(sa.Column("push_token", sa.String(), nullable=False))
        batch_op.add_column(sa.Column("platform", sa.String(), nullable=False))
        batch_op.add_column(sa.Column("environment", sa.String(), nullable=False))
