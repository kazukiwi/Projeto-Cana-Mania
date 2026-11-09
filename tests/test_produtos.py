"""Testes das páginas e ações de produtos."""
from app.models.categoria import Categoria
from app.models.produtos import Produto


def test_tela_produtos_retorna_200(usuario_fake):
    resposta = usuario_fake.get("/produtos/")
    assert resposta.status_code == 200


def test_listar_produtos_sem_login(cliente_sem_login):
    resposta = cliente_sem_login.get("/produtos/")
    assert resposta.status_code == 401


def test_pagina_produtos_mostra_produto_criado(usuario_fake, db_session):
    categoria = Categoria(nome="Camisas")
    db_session.add(categoria)
    db_session.commit()

    produto = Produto(
        nome="Camisa Polo",
        preco=100.0,
        estoque_atual=85,
        categoria_id=categoria.id,
    )
    db_session.add(produto)
    db_session.commit()

    resposta = usuario_fake.get("/produtos/")
    assert resposta.status_code == 200
    assert "Camisa Polo" in resposta.text


def test_criar_produto_pelo_formulario(usuario_fake):
    resposta = usuario_fake.post(
        "/produtos/novo",
        data={"nome": "Boné", "preco": "49.50", "estoque_atual": "15"},
        follow_redirects=False,
    )

    assert resposta.status_code == 302
    assert resposta.headers["location"] == "/produtos?criado=ok"

    resposta_lista = usuario_fake.get("/produtos/")
    assert resposta_lista.status_code == 200
    assert "Boné" in resposta_lista.text
