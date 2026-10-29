"""add calendar event reminders

Revision ID: 5ad475af4daf
Revises: 6bff6c86a5a8
Create Date: 2026-10-06 12:41:18.612408

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5ad475af4daf'
down_revision = '6bff6c86a5a8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("calendar_events", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "reminder_minutes",
                sa.Integer(),
                server_default="15",
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "reminder_sent_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.create_check_constraint(
            "valid_calendar_event_reminder_minutes",
            "reminder_minutes IS NULL OR "
            "reminder_minutes BETWEEN 1 AND 10080",
        )


def downgrade():
    with op.batch_alter_table("calendar_events", schema=None) as batch_op:
        batch_op.drop_constraint(
            "valid_calendar_event_reminder_minutes",
            type_="check",
        )
        batch_op.drop_column("reminder_sent_at")
        batch_op.drop_column("reminder_minutes")
