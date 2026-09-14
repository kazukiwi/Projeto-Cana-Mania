"""criar estoque por tamanho

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e1f2"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "estoques_tamanho",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("produto_id", sa.Integer(), nullable=False),
        sa.Column("tamanho", sa.String(length=10), nullable=False),
        sa.Column("estoque_atual", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["produto_id"], ["produtos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("produto_id", "tamanho", name="uq_estoque_tamanho_produto"),
    )
    op.create_index(op.f("ix_estoques_tamanho_id"), "estoques_tamanho", ["id"], unique=False)

    # O saldo antigo era um total por camiseta; não é possível inferir sua divisão real.
    for tamanho in ("P", "M", "G", "GG"):
        op.execute(
            sa.text(
                "INSERT INTO estoques_tamanho (produto_id, tamanho, estoque_atual) "
                "SELECT id, :tamanho, 0 FROM produtos "
                "WHERE lower(nome) LIKE '%camiseta%'"
            ).bindparams(tamanho=tamanho)
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_estoques_tamanho_id"), table_name="estoques_tamanho")
    op.drop_table("estoques_tamanho")
