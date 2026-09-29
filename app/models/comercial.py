from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text, event, inspect
from sqlalchemy.orm import Session
from app.database import Base
from app.money import Dinheiro

def agora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class MovimentoCaixa(Base):
    __tablename__ = "movimentos_caixa"
    id = Column(Integer, primary_key=True)
    token = Column(String(36), unique=True, nullable=False)
    data = Column(Date, nullable=False, index=True)
    filial = Column(String(40), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    tipo = Column(String(20), nullable=False)
    valor = Column(Dinheiro(), nullable=False)
    motivo = Column(String(255), nullable=False)
    criado_em = Column(DateTime, default=agora_utc, nullable=False)

class ConferenciaCaixa(Base):
    __tablename__ = "conferencias_caixa"
    id = Column(Integer, primary_key=True)
    token = Column(String(36), unique=True, nullable=False)
    data = Column(Date, nullable=False, index=True)
    filial = Column(String(40), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    esperado = Column(Dinheiro(), nullable=False)
    informado = Column(Dinheiro(), nullable=False)
    diferenca = Column(Dinheiro(), nullable=False)
    resumo_json = Column(Text, nullable=False)
    observacao = Column(String(255))
    criado_em = Column(DateTime, default=agora_utc, nullable=False)

class AlteracaoEstoquePreco(Base):
    __tablename__ = "alteracoes_estoque_preco"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"))
    entidade = Column(String(60), nullable=False)
    entidade_id = Column(Integer)
    descricao = Column(String(255), nullable=False)
    campo = Column(String(40), nullable=False)
    anterior = Column(String(100))
    novo = Column(String(100))
    origem = Column(String(100), nullable=False)
    criado_em = Column(DateTime, default=agora_utc, nullable=False, index=True)

@event.listens_for(Session, "before_flush")
def registrar_alteracoes(session, flush_context, instances):
    monitoradas = {
        "produtos": ("preco", "estoque_atual"),
        "estoques_filiais": ("quantidade",),
        "estoques_tamanho": ("estoque_atual",),
        "estoques_variacoes": ("preco", "estoque_atual"),
    }
    for obj in list(session.dirty) + list(session.new):
        tabela = getattr(obj, "__tablename__", "")
        for campo in monitoradas.get(tabela, ()):
            historico = inspect(obj).attrs[campo].history
            if not historico.has_changes():
                continue
            antigo = historico.deleted[0] if historico.deleted else None
            novo = getattr(obj, campo)
            if antigo == novo:
                continue
            descricao = getattr(obj, "nome", None) or f"Produto {getattr(obj, 'produto_id', '')} {getattr(obj, 'filial', '')}"
            session.add(AlteracaoEstoquePreco(
                usuario_id=session.info.get("usuario_id"), entidade=tabela,
                entidade_id=getattr(obj, "id", None), descricao=descricao[:255],
                campo=campo, anterior=str(antigo) if antigo is not None else None,
                novo=str(novo) if novo is not None else None,
                origem=session.info.get("origem", "sistema")[:100],
            ))
