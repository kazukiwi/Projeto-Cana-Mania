"""adicionar estoque por combinacao de tamanho e cor

Revision ID: a9b0c1d2e3f4
Revises: f4a5b6c7d8e9
"""

from alembic import op
import sqlalchemy as sa


revision = "a9b0c1d2e3f4"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "estoques_variacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), nullable=False),
        sa.Column("tamanho_id", sa.Integer(), nullable=False),
        sa.Column("cor", sa.String(length=50), nullable=False),
        sa.Column("estoque_atual", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["produto_id"], ["produtos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tamanho_id"], ["tamanhos.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("produto_id", "tamanho_id", "cor", name="uq_estoque_variacao_produto_tamanho_cor"),
    )
    op.create_index(op.f("ix_estoques_variacoes_id"), "estoques_variacoes", ["id"], unique=False)
    op.add_column("itens_venda", sa.Column("cor", sa.String(length=50), nullable=True))

    # Preserva os produtos antigos com estoque por tamanho como cor "Padrão".
    op.execute(
        "INSERT INTO estoques_variacoes (produto_id, tamanho_id, cor, estoque_atual) "
        "SELECT produto_id, tamanho_id, 'Padrão', estoque_atual FROM estoques_tamanho"
    )


def downgrade() -> None:
    op.drop_column("itens_venda", "cor")
    op.drop_index(op.f("ix_estoques_variacoes_id"), table_name="estoques_variacoes")
    op.drop_table("estoques_variacoes")
