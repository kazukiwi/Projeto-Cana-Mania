"""Testes básicos do cadastro de clientes (usado pelo sistema)."""
from app.models.cliente import Cliente


def test_salvar_cliente_no_banco(db_session):
    cliente = Cliente(nome="Kazuki")
    db_session.add(cliente)
    db_session.commit()

    cliente_salvo = db_session.query(Cliente).filter_by(nome="Kazuki").first()
    assert cliente_salvo is not None
    assert cliente_salvo.nome == "Kazuki"
