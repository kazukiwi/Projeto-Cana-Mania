from app.models.categoria import Categoria
from app.models.produtos import Produto
from app.controllers import rfid_admin_controller


class RFIDSpy:
    def __init__(self):
        self.calls = []

    def iniciar(self, tipo, operador_id, centavos=0):
        self.calls.append((tipo, operador_id, centavos))
        return {"id": "a" * 32, "tipo": tipo, "status": "aguardando_tag"}


def test_pagina_administrativa_de_cartoes(usuario_fake):
    response = usuario_fake.get("/admin/cartoes-rfid")
    assert response.status_code == 200
    assert "Ler cartão" in response.text


def test_total_da_compra_e_calculado_com_preco_do_banco(usuario_fake, db_session, monkeypatch):
    category = Categoria(nome="cookies", ativo=True)
    db_session.add(category)
    db_session.flush()
    db_session.add(Produto(nome="Biscoito RFID", preco=20.0, estoque_atual=9, ativo=True, categoria=category))
    db_session.commit()
    spy = RFIDSpy()
    monkeypatch.setattr(rfid_admin_controller, "obter_rfid", lambda: spy)
    response = usuario_fake.post("/rfid/operacoes", json={
        "tipo": "pagar", "centavos": 2000,
        "carrinho_json": '[{"produto_id":1,"quantidade":1,"preco":0.01}]',
        "desconto_percentual": "", "funcionario_comprador_id": "",
    })
    assert response.status_code == 201
    assert spy.calls == [("pagar", 1, 2000)]


def test_total_enviado_nao_substitui_total_calculado_no_servidor(usuario_fake, db_session, monkeypatch):
    category = Categoria(nome="cookies", ativo=True)
    db_session.add(category)
    db_session.flush()
    db_session.add(Produto(nome="Biscoito RFID", preco=20.0, estoque_atual=9, ativo=True, categoria=category))
    db_session.commit()
    spy = RFIDSpy()
    monkeypatch.setattr(rfid_admin_controller, "obter_rfid", lambda: spy)
    response = usuario_fake.post("/rfid/operacoes", json={
        "tipo": "pagar", "centavos": 1,
        "carrinho_json": '[{"produto_id":1,"quantidade":1}]',
        "desconto_percentual": "0",
    })
    assert response.status_code == 409
    assert spy.calls == []
