"""configurar consumos sem estoque

Revision ID: f9a0b1c2d3e4
Revises: f8a9b0c1d2e3
"""

from alembic import op


revision = "f9a0b1c2d3e4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    categorias = "'abre-alas', 'enredo', 'maniacos por drink'"
    op.execute(
        "DELETE FROM estoques_filiais WHERE produto_id IN ("
        "SELECT produtos.id FROM produtos JOIN categorias ON categorias.id = produtos.categoria_id "
        f"WHERE lower(categorias.nome) IN ({categorias})"
        ")"
    )
    op.execute(
        "UPDATE produtos SET estoque_atual = 0, possui_variacoes_tamanho = 0 WHERE categoria_id IN ("
        f"SELECT id FROM categorias WHERE lower(nome) IN ({categorias})"
        ")"
    )


def downgrade() -> None:
    pass
