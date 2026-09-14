"""recuperar tabela de fechamentos diarios ausente

Revision ID: f4a5b6c7d8e9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa

revision = "f4a5b6c7d8e9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    if "fechamentos_diarios" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "fechamentos_diarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("total_vendido", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quantidade_vendas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fechado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("fechado_automaticamente", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("data", name="uq_fechamentos_diarios_data"),
    )
    op.create_index("ix_fechamentos_diarios_id", "fechamentos_diarios", ["id"])
    op.create_index("ix_fechamentos_diarios_data", "fechamentos_diarios", ["data"])


def downgrade():
    if "fechamentos_diarios" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("fechamentos_diarios")
