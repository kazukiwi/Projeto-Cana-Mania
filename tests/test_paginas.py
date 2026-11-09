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
    assert "<html" in conteudo
    assert "</html>" in conteudo
