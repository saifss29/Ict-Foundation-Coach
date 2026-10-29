"""add user email verification status

Revision ID: a12e118042b7
Revises: 5a344bb0a793
Create Date: 2026-10-04 13:01:22.251082

"""

from alembic import op
import sqlalchemy as sa


revision = "a12e118042b7"
down_revision = "5a344bb0a793"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_email_verified",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )

    users = sa.table(
        "users",
        sa.column("is_email_verified", sa.Boolean()),
    )

    # Preserve access for accounts created before verification existed.
    op.execute(
        users.update().values(is_email_verified=True)
    )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("is_email_verified")