"""add user token version

Revision ID: 5a344bb0a793
Revises: c1c34a7672c4
Create Date: 2026-10-04 12:11:20.677215

"""

from alembic import op
import sqlalchemy as sa


revision = "5a344bb0a793"
down_revision = "c1c34a7672c4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "token_version",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )

        batch_op.create_check_constraint(
            "valid_user_token_version",
            "token_version >= 0",
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(
            "valid_user_token_version",
            type_="check",
        )

        batch_op.drop_column("token_version")