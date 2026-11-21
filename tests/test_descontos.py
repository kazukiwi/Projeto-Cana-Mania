"""Tests for manual sale discounts and courtesy."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.database import Base

with patch.object(Base.metadata, "create_all"):
    from app.controllers.pdv_controller import finalizar_venda


class DescontoVendaTests(unittest.TestCase):
    def finalizar(self, desconto="", cortesia="false", pagamento="dinheiro"):
        produto = SimpleNamespace(id=4, nome="Produto teste", preco=20.0, eh_consumo=True)
        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.with_for_update.return_value.first.return_value = produto
        resposta = finalizar_venda(
            request=None,
            carrinho_json='[{"produto_id": 4, "quantidade": 1}]',
            observacao="",
            funcionario_comprador_id="",
            desconto_manual_percentual=desconto,
            cortesia=cortesia,
            forma_pagamento=pagamento,
            forma_pagamento_2="",
            valor_pagamento_1="",
            valor_pagamento_2="",
            filial="Pinheiros",
            db=db,
            usuario={"id": 1},
        )
        return resposta, db

    def test_aplica_desconto_manual_percentual(self):
        resposta, db = self.finalizar(desconto="25")
        venda = db.add.call_args_list[0].args[0]
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(venda.desconto_percentual, 25)
        self.assertEqual(venda.total_bruto, 20)
        self.assertEqual(venda.total_liquido, 15)
        self.assertIn("Desconto manual: 25%", venda.observacao)

    def test_cortesia_zera_total_e_registra_a_origem(self):
        resposta, db = self.finalizar(cortesia="true", pagamento="cortesia")
        venda = db.add.call_args_list[0].args[0]
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(venda.desconto_percentual, 100)
        self.assertEqual(venda.total_liquido, 0)
        self.assertEqual(venda.forma_pagamento, "cortesia")
        self.assertIn("Cortesia", venda.observacao)

    def test_rejeita_percentual_acima_de_cem(self):
        resposta, db = self.finalizar(desconto="100.01")
        self.assertEqual(resposta.headers["location"], "/pdv?erro=desconto")
        db.add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
