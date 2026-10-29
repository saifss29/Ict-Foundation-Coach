"""link notifications to direct messages

Revision ID: 3c8d7cae9c01
Revises: bed4a13925c1
Create Date: 2026-10-05 13:15:29.827467

"""

from alembic import op
import sqlalchemy as sa


revision = "3c8d7cae9c01"
down_revision = "bed4a13925c1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "notifications",
        schema=None,
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "direct_message_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_unique_constraint(
            "uq_notifications_direct_message_id",
            ["direct_message_id"],
        )

        batch_op.create_foreign_key(
            "fk_notifications_direct_message_id",
            "direct_messages",
            ["direct_message_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table(
        "notifications",
        schema=None,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_notifications_direct_message_id",
            type_="foreignkey",
        )

        batch_op.drop_constraint(
            "uq_notifications_direct_message_id",
            type_="unique",
        )

        batch_op.drop_column("direct_message_id")