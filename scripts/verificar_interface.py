"""Verificação real do navegador com banco em memória e requisições interceptadas."""
import importlib.util
from pathlib import Path
from playwright.sync_api import sync_playwright
from app.models.venda import Venda

spec = importlib.util.spec_from_file_location("test_gestao", "tests/test_gestao.py")
modulo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modulo)
teste = modulo.GestaoTests()
teste.setUp()
saida = Path("backups/previas")
saida.mkdir(parents=True, exist_ok=True)
falhar = {"uma_vez": False}
erros = []

def atender(route):
    request = route.request
    if not request.url.startswith("http://teste.local/"):
        route.abort()
        return
    caminho = request.url.removeprefix("http://teste.local")
    resposta = teste.client.request(request.method, request.url, content=request.post_data_buffer,
                                    headers={k:v for k,v in request.headers.items() if k.lower() not in ("host","content-length")},
                                    follow_redirects=False)
    if caminho == "/pdv/finalizar" and falhar["uma_vez"] and resposta.status_code == 200:
        falhar["uma_vez"] = False
        route.abort()
        return
    headers = {k:v for k,v in resposta.headers.items() if k.lower() not in ("content-length","content-encoding")}
    route.fulfill(status=resposta.status_code, headers=headers, body=resposta.content)

try:
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="msedge", headless=True)
        contexto = navegador.new_context(viewport={"width":1280,"height":900})
        contexto.route("**/*", atender)
        page = contexto.new_page()
        page.on("pageerror", lambda erro: erros.append(str(erro)))
        page.goto("http://teste.local/cardapio")
        assert page.locator(".menu-produto").count() == 3
        page.locator("#cardapio-busca").fill("Drink B")
        assert page.locator(".menu-produto:visible").count() == 1
        page.locator("#cardapio-busca").fill("")
        page.screenshot(path=str(saida/"cardapio-desktop.png"), full_page=True)
        page.locator("#cardapio-tema").click()
        page.set_viewport_size({"width":390,"height":844})
        page.screenshot(path=str(saida/"cardapio-celular-escuro.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.set_viewport_size({"width":1280,"height":900})
        page.goto("http://teste.local/pdv/")
        page.locator("#busca-frozen").fill("Cookie")
        page.locator("#resultado-busca-frozen button").first.click()
        page.locator("#btn-adicionar-carrinho").click()
        page.locator("#forma_pagamento").select_option("dinheiro")
        token = page.locator("#pedido_token").input_value()
        page.reload()
        assert page.locator("#pedido_token").input_value() == token
        assert "Cookie" in page.locator("#corpo-carrinho-pdv").inner_text()
        page.keyboard.press("F2")
        assert page.locator("#busca-frozen").evaluate("el => el === document.activeElement")
        falhar["uma_vez"] = True
        page.locator("#btn-salvar-venda-banco").click()
        page.get_by_role("button",name="Tentar novamente",exact=True).wait_for()
        with teste.Session() as db:
            assert db.query(Venda).count() == 1
        page.get_by_role("button",name="Tentar novamente",exact=True).click()
        page.wait_for_url("**/pdv/venda/*")
        with teste.Session() as db:
            assert db.query(Venda).count() == 1
        page.goto("http://teste.local/pdv/")
        assert page.locator("#corpo-carrinho-pdv").inner_text().strip() == ""
        page.locator("#busca-frozen").fill("Drink A")
        page.locator("#resultado-busca-frozen button").first.click()
        page.locator("#btn-adicionar-carrinho").click()
        page.locator("#forma_pagamento").select_option("dinheiro")
        falhar["uma_vez"] = True
        page.locator("#btn-salvar-venda-banco").click()
        page.get_by_role("button",name="Tentar novamente",exact=True).wait_for()
        page.reload()
        page.wait_for_url("**/pdv/venda/*")
        with teste.Session() as db:
            assert db.query(Venda).count() == 2
        for url,arquivo in (("/relatorios","relatorios.png"),("/caixa","caixa.png")):
            page.goto("http://teste.local"+url)
            page.screenshot(path=str(saida/arquivo), full_page=True)
        page.goto("http://teste.local/relatorios")
        with page.expect_download() as exportacao:
            page.locator('a[download="vendas.csv"]').click()
        assert exportacao.value.suggested_filename == "vendas.csv"
        assert page.locator(".feedback-processando-modal").count() == 0
        navegador.close()
    assert not erros, erros
    print("Navegador: cardápio responsivo, busca, tema, recuperação, atalho e retries sem duplicidade aprovados.")
    print("Prévias: backups/previas/")
finally:
    teste.tearDown()
