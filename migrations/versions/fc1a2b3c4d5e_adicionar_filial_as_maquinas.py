"""add branch to machines

Revision ID: fc1a2b3c4d5e
Revises: fb1c2d3e4f5a
"""
from alembic import op
import sqlalchemy as sa

revision = "fc1a2b3c4d5e"
down_revision = "fb1c2d3e4f5a"
branch_labels = None
depends_on = None


def upgrade():
    colunas = {coluna["name"] for coluna in sa.inspect(op.get_bind()).get_columns("armarios")}
    if "filial" not in colunas:
        op.add_column("armarios", sa.Column("filial", sa.String(length=40), nullable=True))
    op.execute("""
        UPDATE armarios
        SET filial = CASE
            WHEN CAST(numero AS INTEGER) <= 17 THEN 'Pinheiros'
            WHEN CAST(numero AS INTEGER) <= 34 THEN 'Liberdade'
            ELSE 'Carr\u00e3o (F\u00e1brica)'
        END
        WHERE filial IS NULL OR filial = ''
    """)


def downgrade():
    colunas = {coluna["name"] for coluna in sa.inspect(op.get_bind()).get_columns("armarios")}
    if "filial" in colunas:
        op.drop_column("armarios", "filial")
