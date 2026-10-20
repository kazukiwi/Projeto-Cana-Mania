"""adicionar suporte a pagamento dividido no PDV

Revision ID: fb1c2d3e4f5a
Revises: fa0b1c2d3e4f
"""

from alembic import op
import sqlalchemy as sa


revision = "fb1c2d3e4f5a"
down_revision = "fa0b1c2d3e4f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    colunas = {coluna["name"] for coluna in sa.inspect(op.get_bind()).get_columns("vendas")}
    if "forma_pagamento_2" not in colunas:
        op.add_column("vendas", sa.Column("forma_pagamento_2", sa.String(length=30), nullable=True))
    if "valor_pagamento_2" not in colunas:
        op.add_column("vendas", sa.Column("valor_pagamento_2", sa.Float(), nullable=True))


def downgrade() -> None:
    colunas = {coluna["name"] for coluna in sa.inspect(op.get_bind()).get_columns("vendas")}
    if "valor_pagamento_2" in colunas:
        op.drop_column("vendas", "valor_pagamento_2")
    if "forma_pagamento_2" in colunas:
        op.drop_column("vendas", "forma_pagamento_2")
