"""add topic subject and academic level

Revision ID: 0907cc922058
Revises: 774ecd518e43
Create Date: 2026-10-07 11:01:11.958706
"""

from alembic import op
import sqlalchemy as sa


revision = "0907cc922058"
down_revision = "774ecd518e43"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("topics", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "subject",
                sa.String(length=10),
                server_default="ict",
                nullable=False,
            )
        )

        batch_op.add_column(
            sa.Column(
                "academic_level",
                sa.String(length=10),
                server_default="hsc",
                nullable=False,
            )
        )

        batch_op.create_check_constraint(
            "valid_topic_subject",
            "subject IN ('ict', 'math', 'english')",
        )

        batch_op.create_check_constraint(
            "valid_topic_academic_level",
            "academic_level IN ('ssc', 'hsc')",
        )

        batch_op.create_index(
            batch_op.f("ix_topics_subject"),
            ["subject"],
            unique=False,
        )

        batch_op.create_index(
            batch_op.f("ix_topics_academic_level"),
            ["academic_level"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("topics", schema=None) as batch_op:
        batch_op.drop_index(
            batch_op.f("ix_topics_academic_level")
        )

        batch_op.drop_index(
            batch_op.f("ix_topics_subject")
        )

        batch_op.drop_constraint(
            "valid_topic_academic_level",
            type_="check",
        )

        batch_op.drop_constraint(
            "valid_topic_subject",
            type_="check",
        )

        batch_op.drop_column("academic_level")
        batch_op.drop_column("subject")