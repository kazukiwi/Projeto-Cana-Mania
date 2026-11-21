from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func
from app.database import Base

class TransferenciaEstoque(Base):
    __tablename__ = "transferencias_estoque"
    id = Column(Integer, primary_key=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="SET NULL"), nullable=True, index=True)
    produto_nome = Column(String(200), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    usuario_nome = Column(String(100), nullable=False)
    filial_origem = Column(String(40), nullable=False, index=True)
    filial_destino = Column(String(40), nullable=False, index=True)
    quantidade = Column(Integer, nullable=False)
    saldo_origem_anterior = Column(Integer, nullable=False)
    saldo_origem_atualizado = Column(Integer, nullable=False)
    saldo_destino_anterior = Column(Integer, nullable=False)
    saldo_destino_atualizado = Column(Integer, nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now(), index=True)