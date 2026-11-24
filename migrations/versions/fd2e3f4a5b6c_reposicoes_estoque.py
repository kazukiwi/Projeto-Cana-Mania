"""create stock replenishment history

Revision ID: fd2e3f4a5b6c
Revises: fc1a2b3c4d5e
"""
from alembic import op
import sqlalchemy as sa

revision = "fd2e3f4a5b6c"
down_revision = "fc1a2b3c4d5e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reposicoes_estoque",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), nullable=True),
        sa.Column("produto_nome", sa.String(length=200), nullable=False),
        sa.Column("variacao_id", sa.Integer(), nullable=True),
        sa.Column("variacao_label", sa.String(length=120), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("usuario_nome", sa.String(length=100), nullable=False),
        sa.Column("filial", sa.String(length=40), nullable=False),
        sa.Column("local_compra", sa.String(length=150), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("saldo_anterior", sa.Integer(), nullable=False),
        sa.Column("saldo_atualizado", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["produto_id"], ["produtos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["variacao_id"], ["estoques_variacoes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_reposicoes_estoque_produto_id", "reposicoes_estoque", ["produto_id"])
    op.create_index("ix_reposicoes_estoque_usuario_id", "reposicoes_estoque", ["usuario_id"])
    op.create_index("ix_reposicoes_estoque_filial", "reposicoes_estoque", ["filial"])
    op.create_index("ix_reposicoes_estoque_criado_em", "reposicoes_estoque", ["criado_em"])


def downgrade():
    op.drop_index("ix_reposicoes_estoque_criado_em", table_name="reposicoes_estoque")
    op.drop_index("ix_reposicoes_estoque_filial", table_name="reposicoes_estoque")
    op.drop_index("ix_reposicoes_estoque_usuario_id", table_name="reposicoes_estoque")
    op.drop_index("ix_reposicoes_estoque_produto_id", table_name="reposicoes_estoque")
    op.drop_table("reposicoes_estoque")