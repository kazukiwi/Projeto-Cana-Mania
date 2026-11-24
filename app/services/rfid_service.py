"""Camada serial RFID e operações fictícias de saldo mantidas no banco local."""
from __future__ import annotations

import os
import re
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone

from sqlalchemy import update

from app.database import Session as SessionLocal
from app.models.rfid import CartaoRFID, OperacaoRFID


UID_RE = re.compile(r"^[0-9A-F]{8,32}$")
TIPOS = {"identificar", "pagar"}
ATIVOS = {"aguardando_tag", "tag_recebida"}


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RFIDError(RuntimeError):
    pass


class RFIDSerialService:
    """Um leitor por processo; operações e histórico persistem no SQLAlchemy."""

    def __init__(self, session_factory=SessionLocal, serial_factory=None, port=None):
        self._sessions = session_factory
        self._serial_factory = serial_factory
        self._port = port or os.getenv("ARDUINO_PORT")
        self._configured_port = self._port
        self._serial = None
        self._thread = None
        self._lock = threading.RLock()
        self._active: dict | None = None
        self._queue = deque()
        self._pong = threading.Event()
        self._ready = threading.Event()
        self._stop = threading.Event()

    def _connect(self):
        if self._serial is not None and getattr(self._serial, "is_open", True):
            return
        try:
            import serial
        except ImportError as exc:
            raise RFIDError("Dependência pyserial ausente. Instale os requisitos do sistema.") from exc

        if self._configured_port:
            candidatos = [self._configured_port]
        else:
            try:
                from serial.tools import list_ports
                portas = list(list_ports.comports())
            except Exception as exc:
                raise RFIDError(f"Não foi possível localizar portas USB seriais: {exc}") from exc
            identificadores_arduino = {
                (0x2341, 0x0043), (0x2A03, 0x0043), (0x2341, 0x0001), (0x2A03, 0x0001),
                (0x1A86, 0x7523), (0x1A86, 0x5523), (0x10C4, 0xEA60), (0x0403, 0x6001),
            }
            descritores = ("arduino", "ch340", "ch341", "cp210", "usb serial", "usb-serial", "ftdi")
            candidatos = [
                porta.device for porta in portas
                if (getattr(porta, "vid", None), getattr(porta, "pid", None)) in identificadores_arduino
                or any(palavra in " ".join(filter(None, (porta.description, porta.manufacturer))).lower()
                       for palavra in descritores)
            ]
            if not candidatos:
                disponiveis = ", ".join(f"{porta.device} ({porta.description})" for porta in portas) or "nenhuma"
                raise RFIDError(
                    "Arduino não detectado. Conecte a placa por USB e confira se ela aparece no computador. "
                    f"Portas seriais encontradas: {disponiveis}. Se necessário, configure ARDUINO_PORT."
                )

        falhas = []
        for candidato in candidatos:
            porta_serial = None
            try:
                if self._serial_factory:
                    porta_serial = self._serial_factory(candidato, 9600, timeout=0.2, write_timeout=2)
                else:
                    porta_serial = serial.Serial(candidato, 9600, timeout=0.2, write_timeout=2)
                    time.sleep(2.2)  # O Uno reinicia ao abrir a porta USB.
                    porta_serial.reset_input_buffer()
                    porta_serial.write(b"PING\n")
                    porta_serial.flush()
                    prazo = time.monotonic() + 2.5
                    respondeu = False
                    while time.monotonic() < prazo:
                        linha = porta_serial.readline().decode("ascii", errors="replace").strip()
                        if linha == "PONG":
                            respondeu = True
                            break
                    if not respondeu:
                        falhas.append(f"{candidato}: firmware sem resposta ao PING")
                        porta_serial.close()
                        continue
                self._serial = porta_serial
                self._port = candidato
                break
            except Exception as exc:
                if porta_serial is not None:
                    try:
                        porta_serial.close()
                    except Exception:
                        pass
                falhas.append(f"{candidato}: {exc}")

        if self._serial is None:
            if any("firmware sem resposta" in falha for falha in falhas):
                raise RFIDError(
                    "Arduino detectado, mas o sketch não respondeu. Grave hardware/SmartPDV_RFID/SmartPDV_RFID.ino "
                    "na placa usando o Arduino IDE."
                )
            raise RFIDError("Não foi possível abrir uma porta compatível com o Arduino: " + "; ".join(falhas))

        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._listen, daemon=True, name="rfid-serial")
            self._thread.start()
    def close(self):
        self._stop.set()
        serial_port = self._serial
        self._serial = None
        if serial_port is not None:
            try:
                serial_port.close()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def _send(self, line: str):
        try:
            with self._lock:
                if self._serial is None:
                    raise RFIDError("Leitor RFID desconectado.")
                self._serial.write((line + "\n").encode("ascii"))
                self._serial.flush()
        except RFIDError:
            raise
        except Exception as exc:
            raise RFIDError(f"Falha ao enviar comando RFID: {exc}") from exc

    def iniciar(self, tipo: str, operador_id: int, centavos: int = 0, venda_dados=None, usuario=None) -> dict:
        if tipo not in TIPOS or (tipo == "pagar" and not 0 <= centavos <= 99999999):
            raise ValueError("Operacao RFID ou valor invalido.")
        with self._lock:
            self._connect()
            busy = bool(self._active and self._active.get("status") in ATIVOS)
            if usuario and usuario.get("role") in {"cliente", "visitante"}:
                pendentes = ([self._active] if busy else []) + list(self._queue)
                if any(int(ctx.get("usuario", {}).get("id", -1)) == operador_id for ctx in pendentes):
                    raise ValueError("Você já tem um pedido aguardando na maquininha.")
            if tipo == "identificar" and (busy or self._queue):
                raise ValueError("A maquininha está ocupada com outros pedidos.")
            op_id = uuid.uuid4().hex
            db = self._sessions()
            try:
                db.add(OperacaoRFID(operacao_id=op_id, tipo=tipo, status="na_fila" if busy else "aguardando_tag",
                                    valor_centavos=centavos, operador_id=operador_id))
                db.commit()
            finally:
                db.close()
            context = {"id": op_id, "tipo": tipo, "valor": centavos,
                            "status": "aguardando_tag", "uid": None, "started": time.monotonic(),
                            "venda_dados": venda_dados, "usuario": usuario or {"id": operador_id}}
            if busy:
                context["status"] = "na_fila"
                self._queue.append(context)
                return {"id": op_id, "tipo": tipo, "status": "na_fila", "posicao": len(self._queue)}
            self._active = context
            try:
                self._send("IDENTIFICAR" if tipo == "identificar" else f"PAGAR|{centavos}|{op_id[:6].upper()}")
            except RFIDError:
                self._finish_error(op_id, "desconectado")
                raise
            return {"id": op_id, "tipo": tipo, "status": "aguardando_tag"}

    def _proximo(self):
        """Ativa uma operação por vez, seguindo a ordem da fila."""
        with self._lock:
            while self._queue:
                ctx = self._queue.popleft()
                db = self._sessions()
                try:
                    changed = db.execute(update(OperacaoRFID).where(
                        OperacaoRFID.operacao_id == ctx["id"], OperacaoRFID.status == "na_fila"
                    ).values(status="aguardando_tag")).rowcount
                    db.commit()
                finally:
                    db.close()
                if not changed:
                    continue
                ctx["status"], ctx["started"] = "aguardando_tag", time.monotonic()
                self._active = ctx
                try:
                    self._send(f'PAGAR|{ctx["valor"]}|{ctx["id"][:6].upper()}')
                    return
                except RFIDError:
                    self._finish_error(ctx["id"], "desconectado")

    def consultar(self, op_id: str, operador_id: int):
        with self._lock:
            position = next((i for i, ctx in enumerate(self._queue, 1) if ctx["id"] == op_id), None)
        db = self._sessions()
        try:
            op = db.query(OperacaoRFID).filter_by(operacao_id=op_id, operador_id=operador_id).first()
            if not op:
                return None
            card = db.query(CartaoRFID).filter_by(id=op.cartao_id).first() if op.cartao_id else None
            return {"id": op.operacao_id, "tipo": op.tipo, "status": op.status, "uid": op.uid,
                    "posicao": position,
                    "valor_centavos": op.valor_centavos, "saldo_centavos": op.saldo_depois,
                    "nome": card.nome if card else None, "erro": op.erro, "venda_id": op.venda_id}
        finally:
            db.close()

    def cancelar(self, op_id: str, operador_id: int):
        with self._lock:
            for queued in list(self._queue):
                if queued["id"] == op_id and int(queued["usuario"]["id"]) == operador_id:
                    self._queue.remove(queued)
                    db = self._sessions()
                    try:
                        db.query(OperacaoRFID).filter_by(operacao_id=op_id, operador_id=operador_id, status="na_fila").update({"status": "cancelado"})
                        db.commit()
                    finally:
                        db.close()
                    return self.consultar(op_id, operador_id)
            current = self._active
            if not current or current["id"] != op_id or current.get("usuario", {}).get("id") != operador_id or current["status"] not in ATIVOS:
                raise ValueError("A leitura nao esta mais ativa.")
            self._send("CANCELAR")
            self._set_status(op_id, "cancelado")
            current["status"] = "cancelado"
            self._proximo()
            return self.consultar(op_id, operador_id)

    def completar_identificacao(self, op_id: str, operador_id: int, acao: str,
                                nome: str = "", valor_centavos: int = 0):
        if acao not in {"cadastro", "recarga", "consultar"}:
            raise ValueError("Acao RFID invalida.")
        if acao in {"cadastro", "recarga"} and not 1 <= valor_centavos <= 99999999:
            raise ValueError("Informe um valor entre 1 e 99.999.999 centavos.")
        with self._lock:
            current = self._active
            if not current or current["id"] != op_id or current["tipo"] != "identificar" or current["status"] != "tag_recebida":
                raise ValueError("Leitura expirada ou sem cartao identificado. Inicie uma nova leitura.")
            db = self._sessions()
            try:
                op = db.query(OperacaoRFID).filter_by(operacao_id=op_id, operador_id=operador_id).with_for_update().first()
                if not op or op.status != "tag_recebida" or not op.uid:
                    raise ValueError("Operacao RFID invalida ou expirada.")
                card = db.query(CartaoRFID).filter_by(uid=op.uid).with_for_update().first()
                if acao == "cadastro":
                    if card:
                        raise ValueError("Este cartao ja esta cadastrado.")
                    nome = nome.strip()
                    if not nome or len(nome) > 100:
                        raise ValueError("Informe um nome de ate 100 caracteres.")
                    card = CartaoRFID(uid=op.uid, nome=nome, saldo_centavos=valor_centavos, ativo=True)
                    db.add(card)
                    db.flush()
                    op.tipo, op.valor_centavos = "cadastro", valor_centavos
                    op.cartao_id, op.saldo_antes, op.saldo_depois = card.id, 0, valor_centavos
                    op.status = "cadastrado"
                    command = f"CADASTRO_OK|{valor_centavos}"
                elif acao == "recarga":
                    if not card or not card.ativo:
                        raise ValueError("Cartao nao cadastrado ou inativo.")
                    before = card.saldo_centavos
                    changed = db.execute(update(CartaoRFID).where(
                        CartaoRFID.id == card.id, CartaoRFID.ativo.is_(True),
                        CartaoRFID.saldo_centavos <= 2147483647 - valor_centavos
                    ).values(saldo_centavos=CartaoRFID.saldo_centavos + valor_centavos)).rowcount
                    if not changed:
                        raise ValueError("Saldo maximo excedido.")
                    after = db.query(CartaoRFID.saldo_centavos).filter_by(id=card.id).scalar()
                    op.tipo, op.valor_centavos = "recarga", valor_centavos
                    op.cartao_id, op.saldo_antes, op.saldo_depois = card.id, before, after
                    op.status = "recarga_ok"
                    command = f"RECARGA_OK|{after}"
                else:
                    if not card or not card.ativo:
                        raise ValueError("Cartao nao cadastrado ou inativo.")
                    op.cartao_id, op.saldo_antes, op.saldo_depois = card.id, card.saldo_centavos, card.saldo_centavos
                    op.status = "consultado"
                    command = f"SALDO|{card.saldo_centavos}"
                op.concluido_em = _utcnow()
                db.commit()
                saldo = op.saldo_depois
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
            current["status"] = "concluido"
            self._send(command)
            self._proximo()
            return {"id": op_id, "status": current["status"], "saldo_centavos": saldo, "uid": current["uid"]}

    def ping(self, timeout=2):
        self._connect()
        self._pong.clear()
        self._send("PING")
        return self._pong.wait(timeout)

    def _set_status(self, op_id, status, error=None):
        db = self._sessions()
        try:
            op = db.query(OperacaoRFID).filter_by(operacao_id=op_id).first()
            if op and op.status in ATIVOS:
                op.status, op.erro = status, error
                if status not in ATIVOS:
                    op.concluido_em = _utcnow()
                db.commit()
        finally:
            db.close()

    def _finish_error(self, op_id, error):
        self._set_status(op_id, "erro_comunicacao", error)
        if self._active and self._active["id"] == op_id:
            self._active["status"] = "erro_comunicacao"

    def _handle_tag(self, uid):
        if not UID_RE.fullmatch(uid):
            self._send("NEGADO|UID_INVALIDO")
            return
        with self._lock:
            opctx = self._active
            if not opctx or opctx["status"] != "aguardando_tag":
                return
            db = self._sessions()
            try:
                claimed = db.execute(update(OperacaoRFID).where(
                    OperacaoRFID.operacao_id == opctx["id"], OperacaoRFID.status == "aguardando_tag"
                ).values(status="processando")).rowcount
                if not claimed:
                    return
                op = db.query(OperacaoRFID).filter_by(operacao_id=opctx["id"]).with_for_update().first()
                card = db.query(CartaoRFID).filter_by(uid=uid, ativo=True).first()
                op.uid = uid
                opctx["uid"], opctx["status"] = uid, "tag_recebida"
                opctx["started"] = time.monotonic()
                if opctx["tipo"] == "identificar":
                    if card:
                        op.cartao_id = card.id
                        op.saldo_antes = op.saldo_depois = card.saldo_centavos
                        op.status = "tag_recebida"
                        command = f"SALDO|{card.saldo_centavos}"
                    else:
                        op.status = "tag_recebida"
                        command = None
                    db.commit()
                    if command:
                        self._send(command)
                else:
                    if not card:
                        op.status, op.erro = "negado_nao_cadastrado", "NAO_CADASTRADO"
                        op.concluido_em = _utcnow()
                        opctx["status"] = "negado_nao_cadastrado"
                        command = "NEGADO|NAO_CADASTRADO"
                    else:
                        from app.controllers.pdv_controller import finalizar_venda
                        from app.models.venda import Venda
                        from decimal import Decimal
                        dados = opctx.get("venda_dados")
                        if not isinstance(dados, dict):
                            raise ValueError("Dados da venda indisponiveis.")
                        db.info["rfid_venda"] = True
                        response = finalizar_venda(request=None, db=db, usuario=opctx["usuario"], **dados)
                        location = response.headers.get("location", "")
                        if not location.startswith("/pdv/venda/"):
                            db.rollback()
                            self._finish_error(opctx["id"], "Venda invalida ou estoque insuficiente")
                            opctx["status"] = "erro_comunicacao"
                            self._send("NEGADO|ERRO")
                            return
                        sale_id = int(location.split("/pdv/venda/")[1].split("?")[0])
                        sale = db.query(Venda).filter_by(id=sale_id).one()
                        cents = int(Decimal(str(sale.total_liquido)).quantize(Decimal("0.01")) * 100)
                        if cents != opctx["valor"]:
                            db.rollback()
                            self._finish_error(opctx["id"], "Total alterado; inicie novamente")
                            opctx["status"] = "erro_comunicacao"
                            self._send("NEGADO|ERRO")
                            return
                        before = card.saldo_centavos
                        changed = db.execute(update(CartaoRFID).where(
                            CartaoRFID.id == card.id, CartaoRFID.ativo.is_(True),
                            CartaoRFID.saldo_centavos >= cents
                        ).values(saldo_centavos=CartaoRFID.saldo_centavos - cents)).rowcount
                        if not changed:
                            db.rollback()
                            op = db.query(OperacaoRFID).filter_by(operacao_id=opctx["id"]).one()
                            op.uid, op.cartao_id = uid, card.id
                            op.saldo_antes = op.saldo_depois = before
                            op.status, op.erro = "negado_saldo_insuficiente", "SALDO_INSUFICIENTE"
                            command = f"NEGADO|SALDO_INSUFICIENTE|{before}"
                        else:
                            op.cartao_id, op.saldo_antes, op.saldo_depois = card.id, before, before - cents
                            op.venda_id = sale_id
                            op.status = "aprovado"
                            command = f"BRINDE|{op.saldo_depois}" if dados.get("cortesia") == "true" else f"APROVADO|{op.saldo_depois}"
                        op.concluido_em = _utcnow()
                        opctx["status"] = op.status
                    db.commit()
                    self._send(command)
            except Exception as exc:
                db.rollback()
                self._finish_error(opctx["id"], str(exc)[:80])
                try:
                    self._send("NEGADO|ERRO")
                except RFIDError:
                    pass
            finally:
                db.close()
                if opctx["status"] not in ATIVOS:
                    self._proximo()

    def _expire(self):
        with self._lock:
            ctx = self._active
            if not ctx or ctx["status"] not in ATIVOS:
                return
            limit = 120 if ctx["status"] == "aguardando_tag" else 180
            if ctx["tipo"] == "pagar" and ctx["status"] == "tag_recebida":
                limit = 15
            if time.monotonic() - ctx["started"] >= limit:
                self._set_status(ctx["id"], "expirado", "TIMEOUT")
                ctx["status"] = "expirado"
                self._proximo()

    def _listen(self):
        while not self._stop.is_set():
            try:
                line = self._serial.readline().decode("ascii", errors="replace").strip()
            except Exception as exc:
                if self._stop.is_set():
                    return
                with self._lock:
                    if self._active and self._active["status"] in ATIVOS:
                        self._finish_error(self._active["id"], "desconectado")
                    self._serial = None
                    self._proximo()
                return
            self._expire()
            if not line:
                continue
            if line == "READY":
                self._ready.set()
            elif line == "PONG":
                self._pong.set()
            elif line.startswith("TAG|"):
                self._handle_tag(line.split("|", 1)[1].strip().upper())
            elif line == "EXPIRADO":
                with self._lock:
                    if self._active and self._active["status"] in ATIVOS:
                        self._set_status(self._active["id"], "expirado", "TIMEOUT")
                        self._active["status"] = "expirado"
                        self._proximo()
            elif line.startswith("ERRO|"):
                with self._lock:
                    if self._active and self._active["status"] in ATIVOS:
                        error_code = line[5:80]
                        message = ("Arduino recusou o valor. Atualize o sketch da maquininha."
                                   if error_code == "VALOR" else error_code)
                        self._finish_error(self._active["id"], message)
                        self._proximo()


_service = None
_service_lock = threading.Lock()


def obter_rfid() -> RFIDSerialService:
    global _service
    with _service_lock:
        if _service is None:
            db = SessionLocal()
            try:
                db.query(OperacaoRFID).filter(OperacaoRFID.status.in_(["na_fila", "aguardando_tag", "tag_recebida"])).update(
                    {"status": "erro_comunicacao", "erro": "Servidor reiniciado; faça o pedido novamente."}, synchronize_session=False)
                db.commit()
            finally:
                db.close()
            _service = RFIDSerialService()
        return _service


def fechar_rfid():
    global _service
    with _service_lock:
        service, _service = _service, None
    if service is not None:
        service.close()
