"""Pedidos únicos, loja da venda, valores exatos e gestão de caixa."""
from alembic import op
import sqlalchemy as sa

revision = "fb1c2d3e4f5a"
down_revision = "fa0b1c2d3e4f"
branch_labels = None
depends_on = None

MONETARIOS = {
    "produtos": ("preco",),
    "estoques_variacoes": ("preco",),
    "movimentacoes": ("preco_unitario",),
    "vendas": ("total_bruto", "total_liquido"),
    "itens_venda": ("preco_unitario",),
    "fechamentos_diarios": ("total_vendido",),
}

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for tabela, campos in MONETARIOS.items():
        colunas = {c["name"]: c for c in insp.get_columns(tabela)}
        alterar = []
        for campo in campos:
            tipo = colunas[campo]["type"]
            if bind.dialect.name == "sqlite":
                if isinstance(tipo, sa.BigInteger):
                    continue
                op.execute(sa.text(f'UPDATE "{tabela}" SET "{campo}" = ROUND("{campo}" * 100) WHERE "{campo}" IS NOT NULL'))
                destino = sa.BigInteger()
            else:
                if isinstance(tipo, sa.Numeric) and not isinstance(tipo, sa.Float):
                    continue
                destino = sa.Numeric(14, 2)
            alterar.append((campo, tipo, destino))
        if alterar:
            with op.batch_alter_table(tabela) as batch:
                for campo, origem, destino in alterar:
                    batch.alter_column(campo, existing_type=origem, type_=destino)
    colunas = {c["name"] for c in sa.inspect(bind).get_columns("vendas")}
    for nome, tamanho in (("filial", 40), ("pedido_token", 36), ("pedido_hash", 64)):
        if nome not in colunas:
            op.add_column("vendas", sa.Column(nome, sa.String(tamanho), nullable=True))
    indices = {i["name"] for i in sa.inspect(bind).get_indexes("vendas")}
    if "ix_vendas_pedido_token" not in indices:
        op.create_index("ix_vendas_pedido_token", "vendas", ["pedido_token"], unique=True)
    if "ix_vendas_filial" not in indices:
        op.create_index("ix_vendas_filial", "vendas", ["filial"])
    from app.models.comercial import MovimentoCaixa, ConferenciaCaixa, AlteracaoEstoquePreco
    for model in (MovimentoCaixa, ConferenciaCaixa, AlteracaoEstoquePreco):
        model.__table__.create(bind=bind, checkfirst=True)

def downgrade():
    # Retornar ao esquema anterior apagaria conferências e o histórico.
    raise RuntimeError("Restaure o backup anterior à migração para reverter sem perda silenciosa de dados.")
