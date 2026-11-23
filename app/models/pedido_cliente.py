from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func
from app.database import Base


class PedidoCliente(Base):
    __tablename__ = "pedidos_clientes"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(12), nullable=False, unique=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    nome_cliente = Column(String(100), nullable=False)
    itens_json = Column(Text, nullable=False)
    filial = Column(String(80), nullable=False)
    total = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default="aguardando", index=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    chamado_em = Column(DateTime, nullable=True)
    operacao_rfid_id = Column(String(32), nullable=True)
    qr_url = Column(String(500), nullable=True)
