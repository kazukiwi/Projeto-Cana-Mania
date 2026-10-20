"""Exercita os handlers reais sem criar tabelas ou iniciar tarefas agendadas."""
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.database import Base, get_db
from app.auth import get_usuario_logado

with patch.object(Base.metadata, "create_all"):
    from app.main import app


class PixHttpTests(unittest.TestCase):
    def setUp(self):
        self.overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = lambda: MagicMock()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.overrides)

    def autenticar(self):
        app.dependency_overrides[get_usuario_logado] = lambda: {"id": 1}

    def test_sessao_expirada_retorna_json(self):
        resposta = self.client.post("/pdv/pix", data={"filial": "Pinheiros", "carrinho_json": "[]"})
        self.assertEqual(resposta.status_code, 401)
        self.assertIsInstance(resposta.json()["detail"], str)

    def test_carrinho_invalido_retorna_mensagem_real(self):
        self.autenticar()
        resposta = self.client.post("/pdv/pix", data={"filial": "Pinheiros", "carrinho_json": "[]"})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Carrinho", resposta.json()["detail"])

    def test_formulario_incompleto_retorna_json(self):
        self.autenticar()
        resposta = self.client.post("/pdv/pix", data={})
        self.assertEqual(resposta.status_code, 422)
        self.assertIsInstance(resposta.json()["detail"], str)

    def test_erro_inesperado_nao_expoe_detalhes(self):
        self.autenticar()
        def falhar():
            raise RuntimeError("detalhe interno sigiloso")
        app.dependency_overrides[get_db] = falhar
        with patch("app.main.logger.exception"):
            resposta = self.client.post("/pdv/pix", data={"filial": "Pinheiros", "carrinho_json": "[]"})
        self.assertEqual(resposta.status_code, 500)
        self.assertNotIn("sigiloso", resposta.text)
        self.assertIsInstance(resposta.json()["detail"], str)

    def test_paginas_continuam_html(self):
        resposta = self.client.get("/pagina-inexistente-teste")
        self.assertEqual(resposta.status_code, 404)
        self.assertIn("text/html", resposta.headers["content-type"])
