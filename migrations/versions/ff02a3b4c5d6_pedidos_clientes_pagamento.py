"""Add payment fields to existing customer orders."""
from alembic import op
import sqlalchemy as sa


revision = "ff02a3b4c5d6"
down_revision = "ff01a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "pedidos_clientes" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("pedidos_clientes")}
    if "operacao_rfid_id" not in columns:
        op.add_column("pedidos_clientes", sa.Column("operacao_rfid_id", sa.String(length=32), nullable=True))
    if "qr_url" not in columns:
        op.add_column("pedidos_clientes", sa.Column("qr_url", sa.String(length=500), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "pedidos_clientes" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("pedidos_clientes")}
    with op.batch_alter_table("pedidos_clientes") as batch:
        if "qr_url" in columns:
            batch.drop_column("qr_url")
        if "operacao_rfid_id" in columns:
            batch.drop_column("operacao_rfid_id")
