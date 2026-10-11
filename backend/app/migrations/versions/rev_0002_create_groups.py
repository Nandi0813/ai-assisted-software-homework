"""create groups and group_members tables

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
    )
    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(
            ["group_id"], ["groups.id"], name="fk_group_members_group_id_groups"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_group_members_user_id_users"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),
    )


def downgrade() -> None:
    op.drop_table("group_members")
    op.drop_table("groups")
