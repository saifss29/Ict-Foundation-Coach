"""add academic level to users

Revision ID: 9b4549c75c26
Revises: 9819838e7684
Create Date: 2026-10-07 16:15:01.647832
"""

from alembic import op
import sqlalchemy as sa


revision = "9b4549c75c26"
down_revision = "9819838e7684"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "academic_level",
                sa.String(length=10),
                nullable=True,
            )
        )

        batch_op.create_check_constraint(
            "valid_user_academic_level",
            "academic_level IS NULL OR "
            "academic_level IN ('ssc', 'hsc')",
        )

        batch_op.create_check_constraint(
            "teacher_has_no_academic_level",
            "role != 'teacher' OR academic_level IS NULL",
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(
            "teacher_has_no_academic_level",
            type_="check",
        )

        batch_op.drop_constraint(
            "valid_user_academic_level",
            type_="check",
        )

        batch_op.drop_column("academic_level")