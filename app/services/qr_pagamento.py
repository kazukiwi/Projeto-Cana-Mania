"""Confirmações de vendas simuladas por QR Code, sem cobrança bancária."""
import threading
import time
import uuid
from decimal import Decimal

from sqlalchemy import update

from app.database import Session as SessionLocal
from app.models.rfid import OperacaoRFID
from app.models.venda import Venda


class ConfirmacaoQR:
    def __init__(self, sessions=SessionLocal):
        self.sessions = sessions
        self.lock = threading.RLock()
        self.pending = {}

    def expirar(self, operation_id):
        with self.lock:
            pending = self.pending.get(operation_id)
            if pending and time.monotonic() >= pending[0]:
                db = self.sessions()
                try:
                    db.query(OperacaoRFID).filter_by(operacao_id=operation_id, status="aguardando_qr").update({"status": "expirado"})
                    db.commit()
                finally:
                    db.close()
                self.pending.pop(operation_id, None)

    def iniciar(self, operador_id, cents, dados, usuario):
        operation_id = uuid.uuid4().hex
        db = self.sessions()
        try:
            db.add(OperacaoRFID(operacao_id=operation_id, tipo="pagar", status="aguardando_qr",
                                operador_id=operador_id, valor_centavos=cents))
            db.commit()
        finally:
            db.close()
        with self.lock:
            self.pending[operation_id] = (time.monotonic() + 120, dados, usuario, cents)
        return {"id": operation_id, "status": "aguardando_qr"}

    def confirmar(self, operation_id):
        from app.controllers.pdv_controller import finalizar_venda
        with self.lock:
            pending = self.pending.get(operation_id)
            if not pending:
                return "invalido"
            deadline, dados, usuario, cents = pending
            db = self.sessions()
            try:
                if time.monotonic() >= deadline:
                    db.query(OperacaoRFID).filter_by(operacao_id=operation_id, status="aguardando_qr").update({"status": "expirado"})
                    db.commit()
                    self.pending.pop(operation_id, None)
                    return "expirado"
                claimed = db.execute(update(OperacaoRFID).where(
                    OperacaoRFID.operacao_id == operation_id,
                    OperacaoRFID.status == "aguardando_qr"
                ).values(status="processando")).rowcount
                if not claimed:
                    return "invalido"
                db.info["rfid_venda"] = True
                response = finalizar_venda(request=None, db=db, usuario=usuario, **dados)
                location = response.headers.get("location", "")
                if not location.startswith("/pdv/venda/"):
                    raise ValueError("Venda inválida ou estoque insuficiente")
                sale_id = int(location.split("/pdv/venda/")[1].split("?")[0])
                sale = db.query(Venda).filter_by(id=sale_id).one()
                if int(Decimal(str(sale.total_liquido)).quantize(Decimal("0.01")) * 100) != cents:
                    raise ValueError("O total mudou; inicie novamente")
                op = db.query(OperacaoRFID).filter_by(operacao_id=operation_id).one()
                op.status, op.venda_id = "aprovado", sale_id
                db.commit()
                self.pending.pop(operation_id, None)
                return "brinde" if dados.get("cortesia") == "true" else "aprovado"
            except Exception as exc:
                db.rollback()
                db.query(OperacaoRFID).filter_by(operacao_id=operation_id, status="aguardando_qr").update(
                    {"status": "erro_comunicacao", "erro": str(exc)[:80]})
                db.commit()
                self.pending.pop(operation_id, None)
                return "erro"
            finally:
                db.close()


qr_pagamento = ConfirmacaoQR()
