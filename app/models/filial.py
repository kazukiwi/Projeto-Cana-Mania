from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, backref

from app.database import Base


FILIAIS = ("Pinheiros", "Liberdade", "Carrão (Fábrica)")


class EstoqueFilial(Base):
    """Saldo vendável de cada frozen em cada unidade Canamania."""

    __tablename__ = "estoques_filiais"
    __table_args__ = (UniqueConstraint("produto_id", "filial", name="uq_estoque_filial_produto"),)

    id = Column(Integer, primary_key=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False, index=True)
    filial = Column(String(40), nullable=False, index=True)
    quantidade = Column(Integer, nullable=False, default=0)

    produto = relationship("Produto", backref=backref("estoques_filiais", cascade="all, delete-orphan", passive_deletes=True))
