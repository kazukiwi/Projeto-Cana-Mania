"""corrigir coluna ativo ausente em categorias

Revision ID: f8a9b0c1d2e3
Revises: f7a8b9c0d1e2
"""

from alembic import op
import sqlalchemy as sa


revision = "f8a9b0c1d2e3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    colunas = {coluna["name"] for coluna in sa.inspect(op.get_bind()).get_columns("categorias")}
    if "ativo" not in colunas:
        op.add_column(
            "categorias",
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    colunas = {coluna["name"] for coluna in sa.inspect(op.get_bind()).get_columns("categorias")}
    if "ativo" in colunas:
        op.drop_column("categorias", "ativo")
