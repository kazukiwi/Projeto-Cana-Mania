"""adicionar valores para pagamento dividido no PDV

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
    if "valor_pagamento_1" not in colunas:
        op.add_column("vendas", sa.Column("valor_pagamento_1", sa.Float(), nullable=True))
    if "forma_pagamento_2" not in colunas:
        op.add_column("vendas", sa.Column("forma_pagamento_2", sa.String(length=30), nullable=True))
    if "valor_pagamento_2" not in colunas:
        op.add_column("vendas", sa.Column("valor_pagamento_2", sa.Float(), nullable=True))


def downgrade() -> None:
    colunas = {coluna["name"] for coluna in sa.inspect(op.get_bind()).get_columns("vendas")}
    for coluna in ("valor_pagamento_2", "forma_pagamento_2", "valor_pagamento_1"):
        if coluna in colunas:
            op.drop_column("vendas", coluna)
