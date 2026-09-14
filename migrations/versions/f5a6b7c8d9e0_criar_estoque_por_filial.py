"""criar estoque por filial Canamania

Revision ID: f5a6b7c8d9e0
Revises: d4e5f6a7b8c9
"""
from alembic import op
import sqlalchemy as sa

revision = "f5a6b7c8d9e0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "estoques_filiais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filial", sa.String(length=40), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("produto_id", "filial", name="uq_estoque_filial_produto"),
    )
    op.create_index("ix_estoques_filiais_produto_id", "estoques_filiais", ["produto_id"])
    op.create_index("ix_estoques_filiais_filial", "estoques_filiais", ["filial"])


def downgrade():
    op.drop_index("ix_estoques_filiais_filial", table_name="estoques_filiais")
    op.drop_index("ix_estoques_filiais_produto_id", table_name="estoques_filiais")
    op.drop_table("estoques_filiais")
