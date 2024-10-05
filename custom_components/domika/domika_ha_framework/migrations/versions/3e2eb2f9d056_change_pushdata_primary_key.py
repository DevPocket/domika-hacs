"""
change pushdata primary key.

Revision ID: 3e2eb2f9d056
Revises: b81792ef39a1
Create Date: 2024-07-15 15:27:28.006380
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3e2eb2f9d056"
down_revision: Union[str, None] = "b81792ef39a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade step."""
    with op.batch_alter_table("push_data") as batch_op:
        batch_op.drop_constraint("pk_push_data")
        batch_op.create_primary_key(
            "pk_push_data",
            [
                "app_session_id",
                "entity_id",
                "attribute",
            ],
        )


def downgrade() -> None:
    """Downgrade step."""
    with op.batch_alter_table("push_data") as batch_op:
        batch_op.drop_constraint("pk_push_data")
        batch_op.create_primary_key(
            "pk_push_data",
            [
                "event_id",
                "app_session_id",
                "entity_id",
                "attribute",
            ],
        )
