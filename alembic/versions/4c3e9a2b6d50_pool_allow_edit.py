"""pool edit_lock_minutes

Adiciona pools.edit_lock_minutes: janela de reedição do palpite pelo próprio
participante. NULL = definitivo (só admin altera); N = pode alterar até N
minutos antes do início do jogo.

Revision ID: 4c3e9a2b6d50
Revises: 3b2d8e1f9a40
Create Date: 2026-06-29 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4c3e9a2b6d50"
down_revision: Union[str, Sequence[str], None] = "3b2d8e1f9a40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pools",
        sa.Column("edit_lock_minutes", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("pools") as batch:
        batch.drop_column("edit_lock_minutes")
