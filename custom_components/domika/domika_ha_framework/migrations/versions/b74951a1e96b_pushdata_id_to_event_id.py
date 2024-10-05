"""
PushData id to event_id.

Revision ID: b74951a1e96b
Revises: 4c09d7fe055a
Create Date: 2024-05-11 18:11:59.616104
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b74951a1e96b"
down_revision: Union[str, None] = "4c09d7fe055a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade step."""
    with op.batch_alter_table("push_data") as batch_op:
        batch_op.drop_constraint("uq_push_data_app_session_id")
        batch_op.alter_column("id", new_column_name="event_id")

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


def downgrade() -> None:
    """Downgrade step."""
    with op.batch_alter_table("push_data") as batch_op:
        batch_op.alter_column("event_id", new_column_name="id")
        batch_op.create_unique_constraint(
            "uq_push_data_app_session_id",
            [
                "app_session_id",
                "entity_id",
                "attribute",
            ],
        )

    with op.batch_alter_table("push_data") as batch_op:
        batch_op.drop_constraint("pk_push_data")
        batch_op.create_primary_key(
            "pk_push_data",
            [
                "id",
            ],
        )
