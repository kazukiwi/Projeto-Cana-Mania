from threading import RLock, Lock
from types import SimpleNamespace

from app.services.rfid_demo import MaquininhaRFIDDemo


class SerialFakeError(Exception):
    pass


class SerialFake:
    def __init__(self, linha):
        self.linhas = [linha, None]

    def readline(self):
        linha = self.linhas.pop(0)
        if linha is None:
            raise SerialFakeError("fim do teste")
        return linha


def montar_leitor(linha, operacao="pagar"):
    leitor = object.__new__(MaquininhaRFIDDemo)
    leitor._serial_mod = SimpleNamespace(SerialException=SerialFakeError)
    leitor._serial = SerialFake(linha)
    leitor._lock = RLock()
    leitor._serial_lock = Lock()
    leitor._transacoes = {
        "tx-teste": {
            "id": "tx-teste", "centavos": 1250, "status": "aguardando_tag",
            "usuario_id": 7, "operacao": operacao,
        }
    }
    leitor._ativa = "tx-teste"
    return leitor


def test_aprovacao_rfid_confirma_saldo_e_pode_finalizar_venda():
    leitor = montar_leitor(b"APROVADO|1234ABCD|750\n")
    leitor._ouvir()

    transacao = leitor.consultar("tx-teste")
    assert transacao["status"] == "aprovado"
    assert transacao["cartao_uid"] == "1234ABCD"
    assert transacao["saldo_centavos"] == 750
    assert leitor.validar_pagamento("tx-teste", 7, 1250) is not None
    assert leitor.validar_pagamento("tx-teste", 8, 1250) is None
    assert leitor.validar_pagamento("tx-teste", 7, 1000) is None

    leitor.finalizar_pagamento("tx-teste", 42)
    assert leitor.consultar("tx-teste")["status"] == "finalizada"
    assert leitor.validar_pagamento("tx-teste", 7, 1250) is None


def test_saldo_insuficiente_nao_aprova_a_venda():
    leitor = montar_leitor(b"SALDO_INSUFICIENTE|1234ABCD|500\n")
    leitor._ouvir()
    transacao = leitor.consultar("tx-teste")
    assert transacao["status"] == "saldo_insuficiente"
    assert transacao["saldo_centavos"] == 500
    assert leitor.validar_pagamento("tx-teste", 7, 1250) is None


def test_carga_atualiza_estado_sem_finalizar_venda():
    leitor = montar_leitor(b"SALDO_CARREGADO|1234ABCD|5000\n", operacao="carregar")
    leitor._ouvir()
    transacao = leitor.consultar("tx-teste")
    assert transacao["status"] == "saldo_carregado"
    assert transacao["saldo_centavos"] == 5000
    assert leitor.validar_pagamento("tx-teste", 7, 1250) is None