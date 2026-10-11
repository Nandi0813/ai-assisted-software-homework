"""create expenses, expense_shares and payments tables

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("payer_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("split_type", sa.String(10), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_expenses_group_id_groups"),
        sa.ForeignKeyConstraint(["payer_id"], ["users.id"], name="fk_expenses_payer_id_users"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_expenses_created_by_users"),
        sa.CheckConstraint("amount_cents > 0", name="ck_expenses_amount_positive"),
        sa.CheckConstraint(
            "split_type IN ('equal', 'exact', 'percent')",
            name="ck_expenses_split_type_valid",
        ),
    )
    op.create_table(
        "expense_shares",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("percent_bp", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["expense_id"], ["expenses.id"], name="fk_expense_shares_expense_id_expenses"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_expense_shares_user_id_users"),
        sa.UniqueConstraint("expense_id", "user_id", name="uq_expense_shares_expense_user"),
        sa.CheckConstraint("amount_cents >= 0", name="ck_expense_shares_amount_non_negative"),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("from_id", sa.Integer(), nullable=False),
        sa.Column("to_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_payments_group_id_groups"),
        sa.ForeignKeyConstraint(["from_id"], ["users.id"], name="fk_payments_from_id_users"),
        sa.ForeignKeyConstraint(["to_id"], ["users.id"], name="fk_payments_to_id_users"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_payments_created_by_users"),
        sa.CheckConstraint("amount_cents > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint("from_id <> to_id", name="ck_payments_distinct_parties"),
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("expense_shares")
    op.drop_table("expenses")
