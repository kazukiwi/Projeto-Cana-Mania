from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class ReservaArmario(Base):
    __tablename__ = "reservas_armarios"

    id = Column(Integer, primary_key=True, index=True)
    armario_id = Column(Integer, ForeignKey("armarios.id", ondelete="CASCADE"), nullable=False, index=True)
    associado_id = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True, index=True)
    semestre = Column(String(20), nullable=False)
    inicio_em = Column(DateTime, nullable=False)
    fim_em = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default="ativa", index=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)

    armario = relationship("Armario", backref="reservas")
    associado = relationship("Cliente")
