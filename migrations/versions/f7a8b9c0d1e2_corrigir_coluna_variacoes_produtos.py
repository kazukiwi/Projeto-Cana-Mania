"""corrigir coluna de variacoes ausente em produtos

Revision ID: f7a8b9c0d1e2
Revises: f6a7b8c9d0e1
"""

from alembic import op
import sqlalchemy as sa


revision = "f7a8b9c0d1e2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Inclui a coluna que pode faltar em bancos criados por versões antigas."""
    colunas = {coluna["name"] for coluna in sa.inspect(op.get_bind()).get_columns("produtos")}
    if "possui_variacoes_tamanho" not in colunas:
        op.add_column(
            "produtos",
            sa.Column(
                "possui_variacoes_tamanho",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    colunas = {coluna["name"] for coluna in sa.inspect(op.get_bind()).get_columns("produtos")}
    if "possui_variacoes_tamanho" in colunas:
        op.drop_column("produtos", "possui_variacoes_tamanho")
