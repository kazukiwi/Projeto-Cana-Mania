"""Cartoes de saldo ficticio e trilha de auditoria RFID."""
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class CartaoRFID(Base):
    __tablename__ = "cartoes_rfid"
    __table_args__ = (CheckConstraint("saldo_centavos >= 0", name="ck_cartao_rfid_saldo_nao_negativo"),)

    id = Column(Integer, primary_key=True)
    uid = Column(String(32), nullable=False, unique=True, index=True)
    nome = Column(String(100), nullable=False)
    saldo_centavos = Column(Integer, nullable=False, default=0)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class OperacaoRFID(Base):
    __tablename__ = "operacoes_rfid"
    __table_args__ = (
        UniqueConstraint("operacao_id", name="uq_operacao_rfid_id"),
        CheckConstraint("valor_centavos >= 0", name="ck_operacao_rfid_valor_nao_negativo"),
        CheckConstraint("saldo_antes IS NULL OR saldo_antes >= 0", name="ck_operacao_rfid_saldo_antes"),
        CheckConstraint("saldo_depois IS NULL OR saldo_depois >= 0", name="ck_operacao_rfid_saldo_depois"),
    )

    id = Column(Integer, primary_key=True)
    operacao_id = Column(String(32), nullable=False, index=True)
    cartao_id = Column(Integer, ForeignKey("cartoes_rfid.id", ondelete="SET NULL"), nullable=True, index=True)
    uid = Column(String(32), nullable=True, index=True)
    tipo = Column(String(20), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    valor_centavos = Column(Integer, nullable=False, default=0)
    saldo_antes = Column(Integer, nullable=True)
    saldo_depois = Column(Integer, nullable=True)
    operador_id = Column(Integer, nullable=False, index=True)
    erro = Column(String(80), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    concluido_em = Column(DateTime, nullable=True)
