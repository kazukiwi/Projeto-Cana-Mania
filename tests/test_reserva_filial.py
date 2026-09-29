import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.database import Base, get_db
from app.auth import get_usuario_opcional
from app.models.armario import Armario
from app.models.reserva_armario import ReservaArmario
from app.models.filial import FILIAIS
with patch.object(Base.metadata, "create_all"):
    from app.main import app

class ReservaFilialTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread":False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            db.add(Armario(id=1, numero="01", status="disponivel"))
            db.commit()
        self.overrides = app.dependency_overrides.copy()
        def banco():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = banco
        app.dependency_overrides[get_usuario_opcional] = lambda: {"id":1,"role":"admin","nome":"Teste"}
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.overrides)
        self.engine.dispose()

    def test_popup_reserva_para_filial_e_reabre_selecionada(self):
        resposta = self.client.post("/armarios/alterar-status",data={"armario_id":1,"novo_status":"ocupado","filial":"Liberdade"},follow_redirects=False)
        self.assertEqual(resposta.status_code,303)
        with self.Session() as db:
            maquina = db.get(Armario,1)
            self.assertEqual(maquina.associado_nome,"Liberdade")
            self.assertIsNone(maquina.associado_id)
        tela = self.client.get("/maquinas")
        self.assertEqual(tela.status_code,200)
        self.assertIn('data-filial="Liberdade"',tela.text)
        self.assertIn('id="modal-filial"',tela.text)
        self.assertNotIn('id="modal-usuario"',tela.text)
        for filial in FILIAIS:
            self.assertIn(filial,tela.text)

    def test_rejeita_filial_invalida_ou_associado(self):
        for dados in ({"filial":"inexistente"},{"associado_id":123}):
            resposta = self.client.post("/armarios/alterar-status",data={"armario_id":1,"novo_status":"ocupado",**dados},follow_redirects=False)
            self.assertIn("erro=filial",resposta.headers["location"])
        with self.Session() as db:
            self.assertEqual(db.get(Armario,1).status,"disponivel")

    def test_reserva_com_periodo_historico_e_cancelamento(self):
        resposta = self.client.post("/armarios/reservas",data={"armario_id":1,"filial":"Pinheiros","inicio_em":"2026-10-01","fim_em":"2026-10-05"},follow_redirects=False)
        self.assertIn("reserva=ok",resposta.headers["location"])
        with self.Session() as db:
            reserva = db.query(ReservaArmario).one()
            reserva_id = reserva.id
            self.assertEqual(reserva.local_evento,"Pinheiros")
            self.assertIsNone(reserva.associado_id)
        html = self.client.get("/maquinas").text
        self.assertIn('data-destino="Pinheiros"',html)
        self.assertNotIn("Associado removido",html)
        resposta = self.client.post("/armarios/alterar-status",data={"armario_id":1,"novo_status":"disponivel"},follow_redirects=False)
        self.assertIn("erro=reservaativa",resposta.headers["location"])
        self.client.post(f"/armarios/reservas/{reserva_id}/cancelar",follow_redirects=False)
        with self.Session() as db:
            self.assertEqual(db.get(Armario,1).status,"disponivel")
            self.assertEqual(db.get(ReservaArmario,reserva_id).status,"cancelada")

    def test_reserva_agendada_rejeita_filial_invalida(self):
        resposta = self.client.post("/armarios/reservas",data={"armario_id":1,"filial":"Outra","inicio_em":"2026-10-01","fim_em":"2026-10-05"},follow_redirects=False)
        self.assertIn("erro=filial",resposta.headers["location"])
        with self.Session() as db:
            self.assertEqual(db.query(ReservaArmario).count(),0)
