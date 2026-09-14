"""criar tabela armarios

Revision ID: e4f7c8a1b2d3
Revises: b28afd74fc65
Create Date: 2026-06-15 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f7c8a1b2d3"
down_revision: Union[str, Sequence[str], None] = "b28afd74fc65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    armarios = op.create_table(
        "armarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("associado_id", sa.Integer(), nullable=True),
        sa.Column("associado_nome", sa.String(length=150), nullable=True),
        sa.Column("associado_email", sa.String(length=150), nullable=True),
        sa.Column("associado_telefone", sa.String(length=20), nullable=True),
        sa.Column("associado_matricula", sa.String(length=50), nullable=True),
        sa.Column("atribuido_em", sa.String(length=20), nullable=True),
        sa.Column("observacoes", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["associado_id"], ["clientes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_armarios_id"), "armarios", ["id"], unique=False)
    op.create_index(op.f("ix_armarios_numero"), "armarios", ["numero"], unique=True)
    op.create_index(op.f("ix_armarios_status"), "armarios", ["status"], unique=False)

    registros = []
    for i in range(1, 51):
        if i in [1, 5, 12, 25]:
            status = "ocupado"
            nome = "Maria Santos"
            observacoes = ""
        elif i == 20:
            status = "manutencao"
            nome = ""
            observacoes = "Fechadura com defeito"
        else:
            status = "disponivel"
            nome = ""
            observacoes = ""

        registros.append({
            "id": i,
            "numero": str(i).zfill(2),
            "status": status,
            "associado_id": None,
            "associado_nome": nome,
            "associado_email": "maria.santos@email.com" if status == "ocupado" else "",
            "associado_telefone": "(11) 97654-3210" if status == "ocupado" else "",
            "associado_matricula": "AAPM-002" if status == "ocupado" else "",
            "atribuido_em": "04/03/2026" if status == "ocupado" else "",
            "observacoes": observacoes,
        })

    op.bulk_insert(armarios, registros)


def downgrade() -> None:
    op.drop_index(op.f("ix_armarios_status"), table_name="armarios")
    op.drop_index(op.f("ix_armarios_numero"), table_name="armarios")
    op.drop_index(op.f("ix_armarios_id"), table_name="armarios")
    op.drop_table("armarios")
