"""login por username

Adiciona users.username (identificador de login) e torna users.email opcional.

Revision ID: 3b2d8e1f9a40
Revises: 2a1c9f4b7e10
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3b2d8e1f9a40"
down_revision: Union[str, Sequence[str], None] = "2a1c9f4b7e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(), nullable=True))
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    # email passa a ser opcional (login agora é por username)
    with op.batch_alter_table("users") as batch:
        batch.alter_column("email", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
    with op.batch_alter_table("users") as batch:
        batch.alter_column("email", existing_type=sa.String(), nullable=False)
