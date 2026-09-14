from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)

    role = Column(String(100), nullable=False, default="funcionario")
    ativo = Column(Boolean, default=True)
    
    criado_em = Column(DateTime(timezone=True), server_default=func.now())