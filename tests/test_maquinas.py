"""Simple tests for the machine and branch pages."""
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.database import Base
from app.models.filial import FILIAIS

with patch.object(Base.metadata, "create_all"):
    from app.main import alterar_status_armario, cancelar_reserva_armario, criar_reserva_armario


class MaquinasPageTests(unittest.TestCase):
    def test_pagina_separa_maquinas_por_filial_sem_associados(self):
        template = (Path(__file__).parents[1] / "app/templates/armarios/index.html").read_text(encoding="utf-8")
        self.assertIn("grupo-filial", template)
        self.assertIn("modal-filial", template)
        for filial in FILIAIS:
            self.assertIn("{{ filial }}", template)
        self.assertNotIn("Associado", template)
        self.assertNotIn("data-associado", template)

    def test_reserva_mantem_a_filial_da_maquina(self):
        maquina = SimpleNamespace(id=7, status="disponivel", filial="Pinheiros", observacoes="")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [maquina, None]

        resposta = criar_reserva_armario(7, "Evento na filial", date(2026, 11, 10), date(2026, 11, 12), db, usuario=None)

        self.assertEqual(resposta.headers["location"], "/armarios?reserva=ok")
        self.assertEqual(maquina.status, "ocupado")
        self.assertEqual(maquina.filial, "Pinheiros")
        reserva = db.add.call_args.args[0]
        self.assertEqual(reserva.local_evento, "Evento na filial")
        self.assertEqual(reserva.inicio_em, datetime(2026, 11, 10))
        db.commit.assert_called_once()

    def test_atualiza_estado_e_filial_da_maquina(self):
        maquina = SimpleNamespace(id=7, status="disponivel", filial="Pinheiros", observacoes="")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = maquina

        resposta = alterar_status_armario(
            7, "ocupado", FILIAIS[2], db=db, usuario=None
        )

        self.assertEqual(resposta.headers["location"], "/armarios")
        self.assertEqual(maquina.status, "ocupado")
        self.assertEqual(maquina.filial, FILIAIS[2])
        db.commit.assert_called_once()

    def test_rejeita_reserva_com_periodo_invertido(self):
        db = MagicMock()
        resposta = criar_reserva_armario(7, "Evento", date(2026, 11, 12), date(2026, 11, 10), db, usuario=None)
        self.assertEqual(resposta.headers["location"], "/armarios?erro=periodo")
        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_cancela_reserva_e_libera_maquina_sem_mudar_filial(self):
        maquina = SimpleNamespace(id=7, status="ocupado", filial="Liberdade", observacoes="")
        reserva = SimpleNamespace(id=3, status="ativa", armario_id=7, armario=maquina)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [reserva, None]

        resposta = cancelar_reserva_armario(3, db, usuario=None)

        self.assertEqual(resposta.headers["location"], "/armarios?reserva=cancelada")
        self.assertEqual(reserva.status, "cancelada")
        self.assertEqual(maquina.status, "disponivel")
        self.assertEqual(maquina.filial, "Liberdade")
        db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()


def test_pagina_maquinas_mostra_as_tres_filiais(usuario_fake, db_session):
    resposta = usuario_fake.get("/maquinas")
    assert resposta.status_code == 200
    for filial in FILIAIS:
        assert filial in resposta.text
    assert "M?quina 1" in resposta.text or "M&#225;quina 1" in resposta.text
    assert "Associado" not in resposta.text
