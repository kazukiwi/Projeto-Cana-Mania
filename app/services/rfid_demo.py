"""Comunicacao serial com o leitor de cartao pre-pago de teste."""
import os
import threading
import time
import uuid


class RFIDComunicacaoError(RuntimeError):
    pass


class MaquininhaRFIDDemo:
    def __init__(self, porta: str):
        try:
            import serial
        except ImportError as exc:
            raise RFIDComunicacaoError("Dependencia pyserial ausente. Instale os requisitos do projeto.") from exc
        self._serial_mod = serial
        try:
            self._serial = serial.Serial(porta, 9600, timeout=0.2, write_timeout=2)
            time.sleep(2.3)
            self._serial.reset_input_buffer()
        except (serial.SerialException, OSError) as exc:
            raise RFIDComunicacaoError(f"Nao foi possivel abrir a porta {porta}: {exc}") from exc
        self._lock = threading.RLock()
        self._serial_lock = threading.Lock()
        self._transacoes: dict[str, dict] = {}
        self._ativa: str | None = None
        threading.Thread(target=self._ouvir, daemon=True, name="rfid-card-serial").start()

    def _enviar(self, mensagem: str):
        try:
            with self._serial_lock:
                self._serial.write((mensagem + "\n").encode("ascii"))
                self._serial.flush()
        except (self._serial_mod.SerialException, OSError) as exc:
            raise RFIDComunicacaoError(f"Falha na comunicacao serial: {exc}") from exc

    def iniciar(self, centavos: int, usuario_id: int, operacao: str) -> dict:
        with self._lock:
            if self._ativa and self._transacoes[self._ativa]["status"] == "aguardando_tag":
                raise ValueError("Ja existe uma leitura aguardando cartao.")
            identificador = uuid.uuid4().hex
            transacao = {
                "id": identificador, "centavos": centavos,
                "status": "aguardando_tag", "usuario_id": usuario_id,
                "operacao": operacao,
            }
            self._transacoes[identificador] = transacao
            self._ativa = identificador
            try:
                comando = "CARREGAR" if operacao == "carregar" else "PAGAR"
                self._enviar(f"{comando}|{centavos}")
            except RFIDComunicacaoError:
                transacao["status"] = "erro_comunicacao"
                raise
            for antiga in list(self._transacoes)[:-100]:
                self._transacoes.pop(antiga, None)
            return {k: v for k, v in transacao.items() if k != "usuario_id"}

    def consultar(self, identificador: str):
        with self._lock:
            transacao = self._transacoes.get(identificador)
            return dict(transacao) if transacao else None

    def validar_pagamento(self, identificador: str, usuario_id: int, centavos: int):
        with self._lock:
            transacao = self._transacoes.get(identificador)
            if not transacao or transacao.get("usuario_id") != usuario_id:
                return None
            if transacao.get("status") != "aprovado" or transacao.get("operacao") != "pagar":
                return None
            if transacao.get("centavos") != centavos:
                return None
            return dict(transacao)

    def finalizar_pagamento(self, identificador: str, venda_id: int):
        with self._lock:
            transacao = self._transacoes.get(identificador)
            if not transacao or transacao.get("status") != "aprovado":
                raise ValueError("O pagamento RFID nao esta aprovado ou ja foi usado.")
            transacao["status"] = "finalizada"
            transacao["venda_id"] = venda_id

    def cancelar(self, identificador: str):
        with self._lock:
            transacao = self._transacoes.get(identificador)
            if not transacao:
                raise KeyError("Leitura RFID nao encontrada.")
            if transacao["status"] != "aguardando_tag":
                raise ValueError("A leitura ja terminou.")
            self._enviar("CANCELAR")
            transacao["status"] = "cancelado"
            return {k: v for k, v in transacao.items() if k != "usuario_id"}

    def _ouvir(self):
        while True:
            try:
                linha = self._serial.readline().decode("ascii", errors="replace").strip()
            except (self._serial_mod.SerialException, OSError):
                with self._lock:
                    if self._ativa and self._transacoes[self._ativa]["status"] == "aguardando_tag":
                        self._transacoes[self._ativa]["status"] = "erro_comunicacao"
                return
            if not linha:
                continue
            partes = linha.split("|")
            if len(partes) >= 2 and partes[0] in {"APROVADO", "SALDO_INSUFICIENTE", "SALDO_CARREGADO", "ERRO_CARTAO"}:
                uid = partes[1].strip().upper()
                if not uid or any(c not in "0123456789ABCDEF" for c in uid):
                    continue
                try:
                    saldo = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else None
                except ValueError:
                    saldo = None
                status = {
                    "APROVADO": "aprovado",
                    "SALDO_INSUFICIENTE": "saldo_insuficiente",
                    "SALDO_CARREGADO": "saldo_carregado",
                    "ERRO_CARTAO": "erro_cartao",
                }[partes[0]]
                with self._lock:
                    transacao = self._transacoes.get(self._ativa) if self._ativa else None
                    if transacao and transacao["status"] == "aguardando_tag":
                        esperado = "pagar" if status in {"aprovado", "saldo_insuficiente"} else "carregar" if status == "saldo_carregado" else transacao["operacao"]
                        if transacao["operacao"] == esperado:
                            transacao["status"] = status
                            transacao["cartao_uid"] = uid
                            if saldo is not None:
                                transacao["saldo_centavos"] = saldo
                            if status == "erro_cartao":
                                transacao["erro_cartao"] = partes[2] if len(partes) > 2 else "Cartao nao aceito"
            elif linha == "EXPIRADO":
                with self._lock:
                    transacao = self._transacoes.get(self._ativa) if self._ativa else None
                    if transacao and transacao["status"] == "aguardando_tag":
                        transacao["status"] = "expirado"


_instancia: MaquininhaRFIDDemo | None = None
_lock_instancia = threading.Lock()


def obter_maquininha() -> MaquininhaRFIDDemo:
    global _instancia
    with _lock_instancia:
        if _instancia is None:
            _instancia = MaquininhaRFIDDemo(os.getenv("ARDUINO_PORT", "COM3"))
        return _instancia