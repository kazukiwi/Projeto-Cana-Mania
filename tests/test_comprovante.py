import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from starlette.requests import Request

from app.controllers.pdv_controller import detalhe_venda


class ComprovanteTests(unittest.TestCase):
    def test_cupom_com_pagamento_unico_e_dividido(self):
        for dividido in (False, True):
            with self.subTest(dividido=dividido):
                venda = SimpleNamespace(
                    id=42, criado_em=datetime(2026, 11, 3, 12), cliente=None,
                    usuario_id=1, forma_pagamento="dinheiro",
                    forma_pagamento_2="pix" if dividido else None,
                    valor_pagamento_1=10.25 if dividido else 20.50,
                    valor_pagamento_2=10.25 if dividido else None,
                    total_bruto=20.50, total_liquido=20.50,
                    desconto_percentual=0, observacao=None,
                    itens=[SimpleNamespace(produto_nome="Cookie", tamanho=None,
                        cor=None, preco_unitario=10.25, quantidade=2)],
                )
                db = MagicMock()
                db.query.return_value.filter.return_value.first.return_value = venda
                request = Request({"type": "http", "method": "GET", "path": "/pdv/venda/42", "query_string": b"sucesso=ok", "headers": []})
                response = detalhe_venda(42, request, db=db, usuario={"id": 1, "role": "admin", "nome": "Operador"})
                html = response.body.decode("utf-8")
                self.assertEqual(response.status_code, 200)
                self.assertIn("Cookie", html)
                self.assertIn("Imprimir Recibo", html)
                if dividido:
                    self.assertIn("Pix (R$ 10,25)", html)
                    self.assertIn("Dinheiro (R$ 10,25)", html)


if __name__ == "__main__":
    unittest.main()
