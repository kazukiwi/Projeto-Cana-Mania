"""adicionar tamanho ao item da venda

Revision ID: f1a2b3c4d5e6
Revises: e4f7c8a1b2d3
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "e4f7c8a1b2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("itens_venda", sa.Column("tamanho", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("itens_venda", "tamanho")
