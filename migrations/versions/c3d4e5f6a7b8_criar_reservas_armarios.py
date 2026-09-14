"""criar reservas de armarios

Revision ID: c3d4e5f6a7b8
Revises: b9c0d1e2f3a4
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade():
    if "reservas_armarios" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "reservas_armarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("armario_id", sa.Integer(), sa.ForeignKey("armarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("associado_id", sa.Integer(), sa.ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("semestre", sa.String(length=20), nullable=False),
        sa.Column("inicio_em", sa.DateTime(), nullable=False),
        sa.Column("fim_em", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ativa"),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_reservas_armarios_armario_id", "reservas_armarios", ["armario_id"])
    op.create_index("ix_reservas_armarios_associado_id", "reservas_armarios", ["associado_id"])
    op.create_index("ix_reservas_armarios_status", "reservas_armarios", ["status"])


def downgrade():
    if "reservas_armarios" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("reservas_armarios")
