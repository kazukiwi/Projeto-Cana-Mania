"""adicionar forma de pagamento na venda

Revision ID: fa0b1c2d3e4f
Revises: f9a0b1c2d3e4
"""

from alembic import op
import sqlalchemy as sa


revision = "fa0b1c2d3e4f"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    colunas = {coluna["name"] for coluna in sa.inspect(op.get_bind()).get_columns("vendas")}
    if "forma_pagamento" not in colunas:
        op.add_column("vendas", sa.Column("forma_pagamento", sa.String(length=30), nullable=True))


def downgrade() -> None:
    pass
