from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./estoque.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})

Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db(request: Request):
    db = Session()
    from app.auth import get_usuario_opcional
    usuario = get_usuario_opcional(request)
    db.info.update(usuario_id=usuario.get("id") if usuario else None, origem=request.url.path)
    try:
        yield db
    finally:
        db.close()
