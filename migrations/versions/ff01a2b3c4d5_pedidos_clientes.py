"""Create customer order queue."""
from alembic import op
import sqlalchemy as sa

revision = "ff01a2b3c4d5"
down_revision = "fe31a2b4c5d6"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "pedidos_clientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(length=12), nullable=False, unique=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("nome_cliente", sa.String(length=100), nullable=False),
        sa.Column("itens_json", sa.Text(), nullable=False),
        sa.Column("filial", sa.String(length=80), nullable=False),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="aguardando"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("chamado_em", sa.DateTime(), nullable=True),
        sa.Column("operacao_rfid_id", sa.String(length=32), nullable=True),
        sa.Column("qr_url", sa.String(length=500), nullable=True),
    )
    op.create_index("ix_pedidos_clientes_codigo", "pedidos_clientes", ["codigo"], unique=True)
    op.create_index("ix_pedidos_clientes_usuario_id", "pedidos_clientes", ["usuario_id"])
    op.create_index("ix_pedidos_clientes_status", "pedidos_clientes", ["status"])
    op.create_index("ix_pedidos_clientes_criado_em", "pedidos_clientes", ["criado_em"])

def downgrade():
    op.drop_table("pedidos_clientes")
