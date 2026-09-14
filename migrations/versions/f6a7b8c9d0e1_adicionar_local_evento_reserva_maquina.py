"""adicionar local ou evento na reserva de maquina

Revision ID: f6a7b8c9d0e1
Revises: f5a6b7c8d9e0
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("reservas_armarios", sa.Column("local_evento", sa.String(length=150), nullable=True))

def downgrade():
    op.drop_column("reservas_armarios", "local_evento")
