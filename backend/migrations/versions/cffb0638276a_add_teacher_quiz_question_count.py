"""add teacher quiz question count

Revision ID: cffb0638276a
Revises: 8c9ed3cb3586
Create Date: 2026-10-05 16:34:01.759114
"""

from alembic import op
import sqlalchemy as sa


revision = "cffb0638276a"
down_revision = "8c9ed3cb3586"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "teacher_quizzes",
        schema=None,
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "question_count",
                sa.Integer(),
                server_default="5",
                nullable=False,
            )
        )

        batch_op.create_check_constraint(
            "valid_teacher_quiz_question_count",
            "question_count BETWEEN 1 AND 20",
        )


def downgrade():
    with op.batch_alter_table(
        "teacher_quizzes",
        schema=None,
    ) as batch_op:
        batch_op.drop_constraint(
            "valid_teacher_quiz_question_count",
            type_="check",
        )

        batch_op.drop_column("question_count")