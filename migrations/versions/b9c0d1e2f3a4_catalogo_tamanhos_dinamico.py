"""catalogo de tamanhos dinâmico

Revision ID: b9c0d1e2f3a4
Revises: e2f3a4b5c6d7
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa

revision = "b9c0d1e2f3a4"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tamanhos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=30), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("nome", name="uq_tamanhos_nome"),
    )
    op.create_index(op.f("ix_tamanhos_id"), "tamanhos", ["id"], unique=False)
    op.create_index(op.f("ix_tamanhos_nome"), "tamanhos", ["nome"], unique=False)
    for ordem, nome in enumerate(("P", "M", "G", "GG"), start=1):
        op.execute(sa.text("INSERT INTO tamanhos (nome, ordem, ativo) VALUES (:nome, :ordem, :ativo)").bindparams(nome=nome, ordem=ordem, ativo=True))

    with op.batch_alter_table("estoques_tamanho") as batch:
        batch.add_column(sa.Column("tamanho_id", sa.Integer(), nullable=True))
    op.execute(sa.text("UPDATE estoques_tamanho SET tamanho_id = (SELECT id FROM tamanhos WHERE tamanhos.nome = estoques_tamanho.tamanho)"))
    with op.batch_alter_table("estoques_tamanho") as batch:
        batch.alter_column("tamanho_id", nullable=False)
        batch.create_foreign_key("fk_estoques_tamanho_tamanho", "tamanhos", ["tamanho_id"], ["id"], ondelete="RESTRICT")
        batch.create_unique_constraint("uq_estoque_tamanho_produto_id", ["produto_id", "tamanho_id"])
        batch.drop_constraint("uq_estoque_tamanho_produto", type_="unique")
        batch.drop_column("tamanho")


def downgrade() -> None:
    with op.batch_alter_table("estoques_tamanho") as batch:
        batch.add_column(sa.Column("tamanho", sa.String(length=10), nullable=True))
    op.execute(sa.text("UPDATE estoques_tamanho SET tamanho = (SELECT nome FROM tamanhos WHERE tamanhos.id = estoques_tamanho.tamanho_id)"))
    with op.batch_alter_table("estoques_tamanho") as batch:
        batch.alter_column("tamanho", nullable=False)
        batch.create_unique_constraint("uq_estoque_tamanho_produto", ["produto_id", "tamanho"])
        batch.drop_constraint("uq_estoque_tamanho_produto_id", type_="unique")
        batch.drop_constraint("fk_estoques_tamanho_tamanho", type_="foreignkey")
        batch.drop_column("tamanho_id")
    op.drop_index(op.f("ix_tamanhos_nome"), table_name="tamanhos")
    op.drop_index(op.f("ix_tamanhos_id"), table_name="tamanhos")
    op.drop_table("tamanhos")
