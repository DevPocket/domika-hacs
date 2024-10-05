"""
add key-value storage.

Revision ID: 58af1c34e1b2
Revises: 8e9c73bb3020
Create Date: 2024-10-05 17:09:50.169338
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '58af1c34e1b2'
down_revision: Union[str, None] = '8e9c73bb3020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade step."""
    op.create_table(
        "key_value",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint(
            "user_id",
            "key",
            name=op.f("pk_key_value"),
        ),
    )


def downgrade() -> None:
    """Downgrade step."""
    op.drop_table("key_value")
