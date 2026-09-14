"""adicionar preco de venda por variacao

Revision ID: d4e5f6a7b8c9
Revises: a9b0c1d2e3f4
"""

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "estoques_variacoes",
        sa.Column("preco", sa.Float(), nullable=False, server_default="0"),
    )
    # As combinações existentes passam a usar o antigo preço-base do produto.
    op.execute(
        "UPDATE estoques_variacoes "
        "SET preco = (SELECT preco FROM produtos WHERE produtos.id = estoques_variacoes.produto_id)"
    )


def downgrade() -> None:
    op.drop_column("estoques_variacoes", "preco")
