"""create stock transfer history

Revision ID: fd2e3f4a5b6d
Revises: fd2e3f4a5b6c
"""
from alembic import op
import sqlalchemy as sa

revision = "fd2e3f4a5b6d"
down_revision = "fd2e3f4a5b6c"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "transferencias_estoque",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), nullable=True),
        sa.Column("produto_nome", sa.String(length=200), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("usuario_nome", sa.String(length=100), nullable=False),
        sa.Column("filial_origem", sa.String(length=40), nullable=False),
        sa.Column("filial_destino", sa.String(length=40), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("saldo_origem_anterior", sa.Integer(), nullable=False),
        sa.Column("saldo_origem_atualizado", sa.Integer(), nullable=False),
        sa.Column("saldo_destino_anterior", sa.Integer(), nullable=False),
        sa.Column("saldo_destino_atualizado", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["produto_id"], ["produtos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
    )
    for name, column in [("produto_id", "produto_id"), ("usuario_id", "usuario_id"), ("filial_origem", "filial_origem"), ("filial_destino", "filial_destino"), ("criado_em", "criado_em")]:
        op.create_index("ix_transferencias_estoque_" + name, "transferencias_estoque", [column])

def downgrade():
    for name in ["criado_em", "filial_destino", "filial_origem", "usuario_id", "produto_id"]:
        op.drop_index("ix_transferencias_estoque_" + name, table_name="transferencias_estoque")
    op.drop_table("transferencias_estoque")