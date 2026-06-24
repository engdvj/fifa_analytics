"""admin + collection_jobs + bolões flexíveis

Adiciona:
- users.is_admin
- tabela collection_jobs
- scoring_rules.owner_id
- pools.parent_id / scope / is_group

Revision ID: 2a1c9f4b7e10
Revises: 111b44218cf2
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2a1c9f4b7e10"
down_revision: Union[str, Sequence[str], None] = "111b44218cf2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # users.is_admin
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"),
    )

    # scoring_rules.owner_id (FK opcional -> users.id)
    op.add_column("scoring_rules", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_scoring_rules_owner_id_users",
        "scoring_rules",
        "users",
        ["owner_id"],
        ["id"],
    )

    # pools: parent_id (self-FK), scope (JSON), is_group
    op.add_column("pools", sa.Column("parent_id", sa.Integer(), nullable=True))
    op.add_column("pools", sa.Column("scope", sa.JSON(), nullable=True))
    op.add_column(
        "pools",
        sa.Column("is_group", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_pools_parent_id_pools", "pools", "pools", ["parent_id"], ["id"]
    )

    # collection_jobs
    op.create_table(
        "collection_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("log", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("collection_jobs")
    op.drop_constraint("fk_pools_parent_id_pools", "pools", type_="foreignkey")
    op.drop_column("pools", "is_group")
    op.drop_column("pools", "scope")
    op.drop_column("pools", "parent_id")
    op.drop_constraint(
        "fk_scoring_rules_owner_id_users", "scoring_rules", type_="foreignkey"
    )
    op.drop_column("scoring_rules", "owner_id")
    op.drop_column("users", "is_admin")
