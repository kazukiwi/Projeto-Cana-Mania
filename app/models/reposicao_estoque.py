from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class ReposicaoEstoque(Base):
    __tablename__ = "reposicoes_estoque"

    id = Column(Integer, primary_key=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="SET NULL"), nullable=True, index=True)
    produto_nome = Column(String(200), nullable=False)
    variacao_id = Column(Integer, ForeignKey("estoques_variacoes.id", ondelete="SET NULL"), nullable=True)
    variacao_label = Column(String(120), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    usuario_nome = Column(String(100), nullable=False)
    filial = Column(String(40), nullable=False, index=True)
    local_compra = Column(String(150), nullable=False)
    quantidade = Column(Integer, nullable=False)
    saldo_anterior = Column(Integer, nullable=False)
    saldo_atualizado = Column(Integer, nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now(), index=True)