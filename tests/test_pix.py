import unittest
from decimal import Decimal
from unittest.mock import patch
from app.pix import gerar_payload, gerar_pix


def campos(payload):
    resultado = {}
    while payload:
        tag, tamanho = payload[:2], int(payload[2:4])
        resultado[tag] = payload[4:4 + tamanho]
        payload = payload[4 + tamanho:]
    return resultado


class PixTests(unittest.TestCase):
    def test_campos_e_crc(self):
        payload = gerar_payload("fulano@example.com", "Cana Manía", "São Paulo", Decimal("12.35"))
        dados = campos(payload)
        self.assertEqual(dados["54"], "12.35")
        self.assertEqual(dados["59"], "CANA MANIA")
        self.assertEqual(dados["60"], "SAO PAULO")
        self.assertEqual(campos(dados["26"])["01"], "fulano@example.com")
        self.assertEqual(campos(dados["62"])["05"], "***")
        crc = 0xFFFF
        for byte in payload[:-4].encode():
            crc ^= byte << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1) & 0xFFFF
        self.assertEqual(payload[-4:], f"{crc:04X}")

    def test_valores_invalidos(self):
        for valor in (0, -1, "NaN", "Infinity", "abc", "10000000000"):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                gerar_payload("fulano@example.com", "LOJA", "CIDADE", valor)

    def test_configuracao_invalida(self):
        for chave, nome, cidade in (("", "LOJA", "CIDADE"), ("chave invalida", "LOJA", "CIDADE"), ("fulano@example.com", "", "CIDADE"), ("fulano@example.com", "LOJA", "")):
            with self.subTest(chave=chave), self.assertRaises(ValueError):
                gerar_payload(chave, nome, cidade, 1)

    def test_tipos_de_chave(self):
        for chave in ("12345678900", "00038166000105", "12ABC34501DE35", "+5561912345678", "123e4567-e12b-12d1-a456-426655440000"):
            self.assertIn(chave, gerar_payload(chave, "LOJA", "CIDADE", 1))

    def test_imagem_local(self):
        import base64
        from xml.etree import ElementTree
        with patch.dict("os.environ", {"PIX_CHAVE": "fulano@example.com", "PIX_NOME_RECEBEDOR": "LOJA", "PIX_CIDADE": "CIDADE"}):
            pix = gerar_pix("2.50")
        svg = ElementTree.fromstring(base64.b64decode(pix["qr_code"].split(",")[1]))
        self.assertTrue(svg.tag.endswith("svg"))
        self.assertTrue(any(element.tag.endswith("path") for element in svg.iter()))
        self.assertEqual(pix["valor"], "2.50")


class PixEndpointTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from app.controllers.pdv_controller import gerar_pix_carrinho
        self.endpoint = gerar_pix_carrinho
        self.db = MagicMock()
        self.produto = SimpleNamespace(preco=12.5, eh_consumo=True)
        self.db.query.return_value.join.return_value.filter.return_value.first.return_value = self.produto

    def chamar(self, itens, filial="Pinheiros"):
        import json
        return self.endpoint(carrinho_json=json.dumps(itens), filial=filial, db=self.db, usuario={"id": 1})

    def test_preco_do_banco_e_itens_repetidos(self):
        import json
        with patch.dict("os.environ", {"PIX_CHAVE": "fulano@example.com", "PIX_NOME_RECEBEDOR": "LOJA", "PIX_CIDADE": "CIDADE"}):
            resposta = self.chamar([
                {"produto_id": 1, "quantidade": 2, "preco": 0.01},
                {"produto_id": 1, "quantidade": 1, "preco": 0.01},
            ])
        self.assertEqual(json.loads(resposta.body)["valor"], "37.50")
        self.assertEqual(resposta.headers["cache-control"], "no-store")
        self.db.commit.assert_not_called()
        self.db.add.assert_not_called()

    def test_carrinhos_invalidos(self):
        from fastapi import HTTPException
        for itens in ([], {}, [None], [{"produto_id": 1, "quantidade": 1.5}], [{"produto_id": True, "quantidade": 1}], [{"produto_id": 1, "quantidade": -1}]):
            with self.subTest(itens=itens), self.assertRaises(HTTPException):
                self.chamar(itens)

    def test_produto_indisponivel(self):
        from fastapi import HTTPException
        self.db.query.return_value.join.return_value.filter.return_value.first.return_value = None
        with self.assertRaises(HTTPException):
            self.chamar([{"produto_id": 1, "quantidade": 1}])

    def test_estoque_insuficiente(self):
        from types import SimpleNamespace
        from fastapi import HTTPException
        self.produto.eh_consumo = False
        self.db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(quantidade=1)
        with self.assertRaises(HTTPException):
            self.chamar([{"produto_id": 1, "quantidade": 2}])

    def test_loja_invalida(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            self.chamar([{"produto_id": 1, "quantidade": 1}], filial="inexistente")

    def test_preco_invalido_no_banco(self):
        from fastapi import HTTPException
        for preco in (None, float("nan"), -1):
            self.produto.preco = preco
            with self.subTest(preco=preco), self.assertRaises(HTTPException):
                self.chamar([{"produto_id": 1, "quantidade": 1}])
