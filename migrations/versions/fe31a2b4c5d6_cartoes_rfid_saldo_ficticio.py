"""Add RFID demo cards and operation audit trail.

Revision ID: fe31a2b4c5d6
Revises: fd2e3f4a5b6d
"""
from alembic import op
import sqlalchemy as sa

revision = "fe31a2b4c5d6"
down_revision = "fd2e3f4a5b6d"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "cartoes_rfid" not in inspector.get_table_names():
        op.create_table(
            "cartoes_rfid",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uid", sa.String(length=32), nullable=False, unique=True),
            sa.Column("nome", sa.String(length=100), nullable=False),
            sa.Column("saldo_centavos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("saldo_centavos >= 0", name="ck_cartao_rfid_saldo_nao_negativo"),
        )
    if "operacoes_rfid" not in inspector.get_table_names():
        op.create_table(
            "operacoes_rfid",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("operacao_id", sa.String(length=32), nullable=False),
            sa.Column("venda_id", sa.Integer(), sa.ForeignKey("vendas.id"), nullable=True, unique=True),
            sa.Column("cartao_id", sa.Integer(), sa.ForeignKey("cartoes_rfid.id", ondelete="SET NULL"), nullable=True),
            sa.Column("uid", sa.String(length=32), nullable=True),
            sa.Column("tipo", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("valor_centavos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("saldo_antes", sa.Integer(), nullable=True),
            sa.Column("saldo_depois", sa.Integer(), nullable=True),
            sa.Column("operador_id", sa.Integer(), nullable=False),
            sa.Column("erro", sa.String(length=80), nullable=True),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("concluido_em", sa.DateTime(), nullable=True),
            sa.CheckConstraint("valor_centavos >= 0", name="ck_operacao_rfid_valor_nao_negativo"),
            sa.CheckConstraint("saldo_antes IS NULL OR saldo_antes >= 0", name="ck_operacao_rfid_saldo_antes"),
            sa.CheckConstraint("saldo_depois IS NULL OR saldo_depois >= 0", name="ck_operacao_rfid_saldo_depois"),
        )
        op.create_index("ix_operacoes_rfid_operacao_id", "operacoes_rfid", ["operacao_id"])
        op.create_index("ix_operacoes_rfid_cartao_id", "operacoes_rfid", ["cartao_id"])
        op.create_index("ix_operacoes_rfid_uid", "operacoes_rfid", ["uid"])
        op.create_index("ix_operacoes_rfid_status", "operacoes_rfid", ["status"])
        op.create_index("ix_operacoes_rfid_operador_id", "operacoes_rfid", ["operador_id"])
        op.create_index("ix_operacoes_rfid_criado_em", "operacoes_rfid", ["criado_em"])

    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("operacoes_rfid")}
    if "venda_id" not in columns:
        with op.batch_alter_table("operacoes_rfid") as batch:
            batch.add_column(sa.Column("venda_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_operacoes_rfid_venda", "vendas", ["venda_id"], ["id"])
            batch.create_unique_constraint("uq_operacoes_rfid_venda", ["venda_id"])


def downgrade():
    op.drop_table("operacoes_rfid")
    op.drop_table("cartoes_rfid")
