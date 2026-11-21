"""Fixtures simples para os testes das rotas."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from app.database import Base, get_db
from app.auth import get_admin, get_usuario_logado

with patch.object(Base.metadata, "create_all"):
    from app.main import app


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()

    def abrir_banco_teste():
        yield session

    app.dependency_overrides[get_db] = abrir_banco_teste
    yield session
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def usuario_fake(db_session):
    usuario = {"id": 1, "nome": "Teste", "email": "teste@example.com", "role": "admin"}
    app.dependency_overrides[get_usuario_logado] = lambda: usuario
    app.dependency_overrides[get_admin] = lambda: usuario
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def cliente_sem_login(db_session):
    with TestClient(app) as cliente:
        yield cliente
