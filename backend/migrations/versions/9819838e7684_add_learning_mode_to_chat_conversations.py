"""add learning mode to chat conversations

Revision ID: 9819838e7684
Revises: 61ec99df52bd
Create Date: 2026-10-07 14:42:27.631915
"""

from alembic import op
import sqlalchemy as sa


revision = "9819838e7684"
down_revision = "61ec99df52bd"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "chat_conversations",
        schema=None,
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "learning_mode",
                sa.String(length=20),
                server_default="personal_growth",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "valid_chat_conversation_learning_mode",
            "learning_mode IN ('exam_preparation', 'personal_growth')",
        )


def downgrade():
    with op.batch_alter_table(
        "chat_conversations",
        schema=None,
    ) as batch_op:
        batch_op.drop_constraint(
            "valid_chat_conversation_learning_mode",
            type_="check",
        )
        batch_op.drop_column("learning_mode")