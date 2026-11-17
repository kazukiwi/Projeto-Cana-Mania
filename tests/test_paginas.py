"""Testes básicos das páginas do sistema."""
from pathlib import Path

import pytest


PAGINAS_PUBLICAS = [
    "/",
    "/termos-de-uso",
    "/politica-de-privacidade",
    "/suporte",
    "/auth/esqueci-senha",
]
TEMPLATES = sorted(
    path
    for path in (Path(__file__).parents[1] / "app" / "templates").rglob("*.html")
    if "partials" not in path.parts
)


@pytest.mark.parametrize("url", PAGINAS_PUBLICAS)
def test_pagina_publica_abre_em_html(usuario_fake, url):
    resposta = usuario_fake.get(url)
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda path: path.name)
def test_template_de_pagina_tem_conteudo_html(template):
    conteudo = template.read_text(encoding="utf-8-sig").lower()
    assert conteudo.strip()
    assert "{% extends" in conteudo or "<html" in conteudo
    if "{% extends" not in conteudo:
        assert "</html>" in conteudo


def test_pagina_insights_abre_para_usuario_autenticado(usuario_fake):
    resposta = usuario_fake.get("/insights/")
    assert resposta.status_code == 200
    assert "Vendas por dia" in resposta.text
    assert "Chamar cliente pelo ID" in resposta.text


def test_busca_cliente_por_id_oferece_contato(usuario_fake, db_session):
    from app.models.cliente import Cliente

    cliente = Cliente(nome="Cliente Teste", telefone="11987654321", ativo=True)
    db_session.add(cliente)
    db_session.commit()

    resposta = usuario_fake.get(f"/insights/?cliente_id={cliente.id}")
    assert resposta.status_code == 200
    assert "Cliente Teste" in resposta.text
    assert "tel:11987654321" in resposta.text
    assert "https://wa.me/5511987654321" in resposta.text