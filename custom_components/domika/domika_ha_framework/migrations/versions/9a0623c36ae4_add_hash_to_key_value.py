"""
add hash to key-value.

Revision ID: 9a0623c36ae4
Revises: 58af1c34e1b2
Create Date: 2024-10-06 15:01:36.476849
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9a0623c36ae4'
down_revision: Union[str, None] = '58af1c34e1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade step."""
    with op.batch_alter_table("key_value") as batch_op:
        batch_op.add_column(sa.Column("hash", sa.String(), nullable=False, server_default=""))

    with op.batch_alter_table("key_value") as batch_op:
        batch_op.alter_column("hash", server_default=None)


def downgrade() -> None:
    """Downgrade step."""
    with op.batch_alter_table("key_value") as batch_op:
        batch_op.drop_column("hash")
