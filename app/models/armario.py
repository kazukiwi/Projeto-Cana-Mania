from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Armario(Base):
    __tablename__ = "armarios"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(10), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="disponivel", index=True)

    associado_id = Column(
        Integer,
        ForeignKey("clientes.id", ondelete="SET NULL"),
        nullable=True
    )
    associado_nome = Column(String(150), nullable=True)
    associado_email = Column(String(150), nullable=True)
    associado_telefone = Column(String(20), nullable=True)
    associado_matricula = Column(String(50), nullable=True)
    atribuido_em = Column(String(20), nullable=True)
    observacoes = Column(String(255), nullable=True)

    associado = relationship("Cliente", backref="armarios")
