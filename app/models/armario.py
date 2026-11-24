from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Armario(Base):
    __tablename__ = "armarios"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(10), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="disponivel", index=True)
    filial = Column(String(40), nullable=False, default="Pinheiros", server_default="Pinheiros")
    observacoes = Column(String(255), nullable=True)

    reservas = relationship("ReservaArmario", back_populates="armario")
