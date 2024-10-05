"""
add original timestamp and domain to pushdata / events.

Revision ID: 8e9c73bb3020
Revises: 939806f0fa92
Create Date: 2024-08-09 13:30:00.613583
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8e9c73bb3020"
down_revision: Union[str, None] = "939806f0fa92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade step."""
    with op.batch_alter_table("push_data", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "delay",
                sa.Integer(),
                server_default="0",
                nullable=False,
            ),
            insert_after="timestamp",
        )

    with op.batch_alter_table("events", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "delay",
                sa.Integer(),
                server_default="0",
                nullable=False,
            ),
            insert_after="timestamp",
        )


def downgrade() -> None:
    """Downgrade step."""
    with op.batch_alter_table("push_data") as batch_op:
        batch_op.drop_column("delay")

    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_column("delay")
