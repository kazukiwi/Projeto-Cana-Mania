"""criar tabela de fechamentos diarios

Revision ID: d2e3f4a5b6c7
Revises: a7b8c9d0e1f2
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa


revision = "d2e3f4a5b6c7"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fechamentos_diarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("total_vendido", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quantidade_vendas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fechado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("fechado_automaticamente", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("data", name="uq_fechamentos_diarios_data"),
    )
    op.create_index(op.f("ix_fechamentos_diarios_id"), "fechamentos_diarios", ["id"], unique=False)
    op.create_index(op.f("ix_fechamentos_diarios_data"), "fechamentos_diarios", ["data"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fechamentos_diarios_data"), table_name="fechamentos_diarios")
    op.drop_index(op.f("ix_fechamentos_diarios_id"), table_name="fechamentos_diarios")
    op.drop_table("fechamentos_diarios")
