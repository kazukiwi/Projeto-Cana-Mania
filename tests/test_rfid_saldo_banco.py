import threading
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.rfid import CartaoRFID, OperacaoRFID
from app.services.rfid_service import RFIDSerialService


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.is_open = True
        self.writes = []
        self.closed = threading.Event()
        self.broken = threading.Event()

    def write(self, data):
        self.writes.append(data.decode("ascii").strip())
        return len(data)

    def flush(self):
        pass

    def readline(self):
        if self.broken.is_set():
            raise OSError("serial disconnected")
        if self.closed.is_set():
            raise OSError("serial closed")
        self.broken.wait(0.02)
        return b""

    def close(self):
        self.closed.set()
        self.is_open = False


@pytest.fixture
def rfid_env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    serial = FakeSerial()
    manager = RFIDSerialService(factory, serial_factory=lambda *a, **kw: serial, port="fake")
    yield manager, factory, serial
    manager.close()
    engine.dispose()


def test_registra_duas_tags_com_saldos_independentes(rfid_env):
    manager, factory, serial = rfid_env
    for uid, cents in (("04A1B2C3", 5000), ("04D4E5F6", 8250)):
        operation = manager.iniciar("identificar", 7)
        manager._handle_tag(uid)
        result = manager.completar_identificacao(operation["id"], 7, "cadastro", f"Cartao {uid}", cents)
        assert result["saldo_centavos"] == cents
    with factory() as db:
        cards = db.query(CartaoRFID).order_by(CartaoRFID.uid).all()
        assert [(card.uid, card.saldo_centavos) for card in cards] == [("04A1B2C3", 5000), ("04D4E5F6", 8250)]
    assert "CADASTRO_OK|5000" in serial.writes and "CADASTRO_OK|8250" in serial.writes


def test_recarga_consulta_e_historico(rfid_env):
    manager, factory, serial = rfid_env
    identify = manager.iniciar("identificar", 7)
    manager._handle_tag("04A1B2C3")
    manager.completar_identificacao(identify["id"], 7, "cadastro", "Teste", 5000)
    reload_op = manager.iniciar("identificar", 7)
    manager._handle_tag("04A1B2C3")
    updated = manager.completar_identificacao(reload_op["id"], 7, "recarga", valor_centavos=7500)
    assert updated["saldo_centavos"] == 12500
    assert "SALDO|5000" in serial.writes
    assert "RECARGA_OK|12500" in serial.writes
    with factory() as db:
        history = db.query(OperacaoRFID).filter_by(cartao_id=1).order_by(OperacaoRFID.id).all()
        assert [row.tipo for row in history] == ["cadastro", "recarga"]
        assert history[1].saldo_antes == 5000 and history[1].saldo_depois == 12500


def test_compra_aprovada_debita_em_centavos_e_gera_resultado_unico(rfid_env):
    manager, factory, serial = rfid_env
    with factory() as db:
        db.add(CartaoRFID(uid="04A1B2C3", nome="Teste", saldo_centavos=5000))
        db.commit()
    purchase = manager.iniciar("pagar", 9, 2000)
    manager._handle_tag("04A1B2C3")
    manager._handle_tag("04A1B2C3")
    with factory() as db:
        card = db.query(CartaoRFID).filter_by(uid="04A1B2C3").one()
        op = db.query(OperacaoRFID).filter_by(operacao_id=purchase["id"]).one()
        assert card.saldo_centavos == 3000
        assert (op.status, op.saldo_antes, op.saldo_depois) == ("aprovado", 5000, 3000)
    assert serial.writes.count("APROVADO|3000") == 1


def test_saldo_insuficiente_nao_deixa_saldo_negativo(rfid_env):
    manager, factory, serial = rfid_env
    with factory() as db:
        db.add(CartaoRFID(uid="04A1B2C3", nome="Teste", saldo_centavos=1500))
        db.commit()
    purchase = manager.iniciar("pagar", 9, 2000)
    manager._handle_tag("04A1B2C3")
    with factory() as db:
        card = db.query(CartaoRFID).filter_by(uid="04A1B2C3").one()
        op = db.query(OperacaoRFID).filter_by(operacao_id=purchase["id"]).one()
        assert card.saldo_centavos == 1500
        assert op.status == "negado_saldo_insuficiente"
    assert "NEGADO|SALDO_INSUFICIENTE|1500" in serial.writes


def test_tag_nao_cadastrada_e_negada_sem_criar_saldo(rfid_env):
    manager, factory, serial = rfid_env
    purchase = manager.iniciar("pagar", 9, 2000)
    manager._handle_tag("04A1B2C3")
    with factory() as db:
        assert db.query(CartaoRFID).count() == 0
        assert db.query(OperacaoRFID).filter_by(operacao_id=purchase["id"]).one().status == "negado_nao_cadastrado"
    assert "NEGADO|NAO_CADASTRADO" in serial.writes


def test_desconexao_e_expiracao_encerram_operacao_e_nova_leitura_tem_id_novo(rfid_env):
    manager, factory, serial = rfid_env
    first = manager.iniciar("identificar", 7)
    serial.broken.set()
    deadline = time.monotonic() + 2
    while manager.consultar(first["id"], 7)["status"] != "erro_comunicacao" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert manager.consultar(first["id"], 7)["status"] == "erro_comunicacao"
    manager._thread.join(timeout=1)
    serial.broken.clear()
    second = manager.iniciar("identificar", 7)
    manager._active["started"] = time.monotonic() - 121
    manager._expire()
    assert manager.consultar(second["id"], 7)["status"] == "expirado"
    third = manager.iniciar("identificar", 7)
    assert third["id"] not in {first["id"], second["id"]}
    with factory() as db:
        assert db.query(OperacaoRFID).filter_by(status="expirado").count() == 1


def test_operacao_de_recarga_nao_pode_ser_reutilizada(rfid_env):
    manager, factory, _ = rfid_env
    with factory() as db:
        db.add(CartaoRFID(uid="04A1B2C3", nome="Teste", saldo_centavos=1000))
        db.commit()
    operation = manager.iniciar("identificar", 7)
    manager._handle_tag("04A1B2C3")
    manager.completar_identificacao(operation["id"], 7, "recarga", valor_centavos=500)
    with pytest.raises(ValueError):
        manager.completar_identificacao(operation["id"], 7, "recarga", valor_centavos=500)
    with factory() as db:
        assert db.query(CartaoRFID).filter_by(uid="04A1B2C3").one().saldo_centavos == 1500
