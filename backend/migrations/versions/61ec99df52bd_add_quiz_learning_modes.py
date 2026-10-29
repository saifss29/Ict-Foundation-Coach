"""add quiz learning modes

Revision ID: 61ec99df52bd
Revises: 0907cc922058
Create Date: 2026-10-07 11:34:46.771857
"""

from alembic import op
import sqlalchemy as sa


revision = "61ec99df52bd"
down_revision = "0907cc922058"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "generated_quizzes",
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
            "valid_generated_quiz_learning_mode",
            "learning_mode IN ('exam_preparation', 'personal_growth')",
        )

    with op.batch_alter_table(
        "teacher_quizzes",
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
            "valid_teacher_quiz_learning_mode",
            "learning_mode IN ('exam_preparation', 'personal_growth')",
        )


def downgrade():
    with op.batch_alter_table(
        "teacher_quizzes",
        schema=None,
    ) as batch_op:
        batch_op.drop_constraint(
            "valid_teacher_quiz_learning_mode",
            type_="check",
        )

        batch_op.drop_column("learning_mode")

    with op.batch_alter_table(
        "generated_quizzes",
        schema=None,
    ) as batch_op:
        batch_op.drop_constraint(
            "valid_generated_quiz_learning_mode",
            type_="check",
        )

        batch_op.drop_column("learning_mode")