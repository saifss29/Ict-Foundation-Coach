"""add teacher student role to users

Revision ID: a83dd3480abc
Revises: c710307b7bb9
Create Date: 2026-10-01 10:46:36.050606
"""

from alembic import op
import sqlalchemy as sa


revision = "a83dd3480abc"
down_revision = "c710307b7bb9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "role",
                sa.String(length=20),
                nullable=False,
                server_default="student",
            )
        )
        batch_op.create_check_constraint(
            "valid_user_role",
            "role IN ('student', 'teacher')",
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(
            "valid_user_role",
            type_="check",
        )
        batch_op.drop_column("role")